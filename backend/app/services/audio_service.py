"""File-based STT routing; reuse credential selection, admission and HTTP pools."""
import asyncio
import json
import time
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from app.adapters.factory import get_adapter
from app.adapters.openai import GenericOpenAIAdapter
from app.core.admission import admission
from app.core.circuit_breaker import circuit_breaker
from app.core.crypto import decrypt_secret
from app.core.errors import ErrorCategory, RouterException
from app.routing.engine import RoutingEngine
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.services.log_service import LogService
from app.services.proxy_service import ProxyService
from app.services.quota_service import QuotaService

# ponytail: fixed free-tier-safe upload ceiling; raise with plan-aware limits if needed.
MAX_AUDIO_BYTES = 25_000_000
AUDIO_EXTENSIONS = {'flac', 'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'ogg', 'wav', 'webm'}
AUDIO_ENDPOINT = '/audio/transcriptions'


def is_transcription_model(model_id, endpoints=()):
    native = model_id.rsplit('/', 1)[-1].lower().split(':', 1)[0]
    return native == 'whisper' or native == 'whisper-1' or native.startswith(('whisper-', 'distil-whisper-')) or any(
        endpoint.rstrip('/').endswith(AUDIO_ENDPOINT) for endpoint in endpoints or ())


def audio_metadata(capabilities):
    return {**(capabilities or {}), 'chat': False, 'streaming': False, 'tools': False,
            'audio_input': True, 'audio_output': False, 'transcription': True}


class TranscriptionRequest(BaseModel):
    is_audio_transcription: ClassVar[bool] = True
    model: str = Field(min_length=1, max_length=150)
    language: str | None = Field(default=None, pattern=r'^[a-z]{2}$')
    prompt: str | None = Field(default=None, max_length=4096)
    response_format: Literal['json', 'verbose_json', 'text'] = 'json'
    temperature: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    timestamp_granularities: list[Literal['word', 'segment']] = Field(default_factory=list, max_length=2)

    @model_validator(mode='after')
    def validate_timestamps(self):
        if self.timestamp_granularities and self.response_format != 'verbose_json':
            raise ValueError('timestamp_granularities[] requires response_format=verbose_json')
        if not self.model.strip():
            raise ValueError('model must not be blank')
        self.model = self.model.strip()
        return self


class AudioService:
    @staticmethod
    async def transcribe(db, payload, audio, filename, content_type, *, router_key=None, request_id):
        if router_key is not None:
            RoutingEngine._check_permissions(router_key, payload.model)
        # ponytail: direct models only; profile composition belongs here when requested.
        if payload.model.startswith(('route/', 'fusion/', 'judge/', 'smart/')):
            raise RouterException('Audio transcription requires a direct audio model', ErrorCategory.INVALID_REQUEST)
        candidates = await RoutingEngine._get_candidate_credentials_for_model(db, payload.model)
        if not candidates:
            await RoutingEngine._raise_no_candidates(db, payload.model, request_id)
        candidates = [(cred, model) for cred, model in candidates if model.model_type == 'audio' or
                      is_transcription_model(model.provider_model_id, model.supported_endpoints)]
        if not candidates:
            raise RouterException('Selected model is not an audio transcription model', ErrorCategory.INVALID_REQUEST)
        # Canonical permission checks also prevent raw IDs bypassing an allowlist.
        if router_key is not None:
            RoutingEngine._check_permissions(router_key, candidates[0][1].canonical_slug)
            if router_key.rate_limit_tpm is not None:
                raise RouterException('Token TPM limits cannot meter audio seconds', ErrorCategory.RATE_LIMIT, status_code=429)
            from app.services.api_key_service import ApiKeyService
            await ApiKeyService.admit_inference(db, router_key, requested_model=candidates[0][1].canonical_slug)

        started = time.perf_counter()
        attempts, result, last_error = [], None, None
        resolved_cred = resolved_model = None
        for cred, model in candidates:
            provider = model.provider
            adapter = get_adapter(provider.adapter_type)
            if not isinstance(adapter, GenericOpenAIAdapter):
                raise RouterException('Selected provider does not support the audio transcription protocol', ErrorCategory.INVALID_REQUEST)
            if not RoutingEngine._eligible(provider, model, cred):
                continue
            proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
            if cred.proxy and not cred.proxy.enabled:
                raise RouterException('Selected credential proxy is disabled', ErrorCategory.INVALID_REQUEST)
            quota = reservation = dispatch = None
            dispatched = credential_admission = False
            attempt_started = time.perf_counter()
            try:
                if cred.tpm_limit is not None:
                    raise RouterException('Credential token TPM limits cannot meter audio seconds', ErrorCategory.RATE_LIMIT,
                        status_code=429, raw_error={'local_admission': True, 'credential_id': cred.id})
                quota, _ = await QuotaService.reserve_dispatch(provider, model, payload, credential=cred)
                credential_admission = True
                reservation = admission.reserve('credential', cred.id, rpm=cred.rpm_limit, concurrency=cred.max_concurrency)
                credential_admission = False
                trace_request = ChatCompletionRequest(model=payload.model, messages=[ChatMessage(role='user', content=payload.prompt or '')])
                dispatch = LogService.start_dispatch(provider, model, trace_request, stream=False)
                if dispatch is not None:
                    dispatch['parameters'] = {'endpoint': AUDIO_ENDPOINT, 'response_format': payload.response_format,
                                              'language': payload.language, 'temperature': payload.temperature}
                    dispatch['prices'] = None  # STT is billed in seconds, not text tokens.
                dispatched = True
                async with asyncio.timeout(120):
                    result = await adapter.transcribe_audio(base_url=provider.base_url, api_key=decrypt_secret(cred.encrypted_api_key),
                        model_id=model.provider_model_id, payload=payload, audio=audio, filename=filename,
                        content_type=content_type, extra_headers=provider.extra_headers,
                        configuration=provider.configuration or {}, proxy_url=proxy_url, timeout=120)
                circuit_breaker.record_success(cred.id, model.provider_model_id)
                resolved_cred, resolved_model = cred, model
                LogService.finish_dispatch(dispatch, 'SUCCESS', (time.perf_counter() - attempt_started) * 1000)
                attempts.append({'attempt_number': len(attempts) + 1, 'provider_name': provider.name,
                    'credential_name': cred.name, 'model_name': model.provider_model_id, 'status': 'SUCCESS',
                    'http_status': 200, 'latency_ms': (time.perf_counter() - attempt_started) * 1000})
                break
            except Exception as exc:
                last_error = exc if isinstance(exc, RouterException) else adapter.normalize_error(exception=exc)
                if not isinstance(exc, RouterException) and dispatched:
                    last_error.replay_safe = False
                metadata = last_error.raw_error if isinstance(last_error.raw_error, dict) else {}
                local = bool(metadata.get('local_admission')) and not dispatched
                credential_local = local and (credential_admission or metadata.get('credential_id') == cred.id)
                if not local:
                    circuit_breaker.record_failure(cred.id, last_error.category, last_error.retry_after, last_error.message, model.provider_model_id)
                LogService.finish_dispatch(dispatch, 'FAILED', (time.perf_counter() - attempt_started) * 1000)
                attempts.append({'attempt_number': len(attempts) + 1, 'provider_name': provider.name,
                    'credential_name': cred.name, 'model_name': model.provider_model_id, 'status': 'FAILED',
                    'http_status': last_error.status_code, 'error_category': last_error.category.value,
                    'error_message': last_error.message, 'latency_ms': (time.perf_counter() - attempt_started) * 1000})
                if local and not credential_local or not (credential_local or last_error.is_fallback_eligible or
                        last_error.replay_safe and last_error.category == ErrorCategory.AUTH_ERROR):
                    break
            finally:
                if reservation is not None:
                    reservation.finish()
                if quota is not None:
                    await quota.finish(success=result is not None, dispatched=dispatched)
                if dispatch is not None and dispatch['status'] == 'RUNNING':
                    LogService.finish_dispatch(dispatch, 'CANCELLED', (time.perf_counter() - attempt_started) * 1000)

        await LogService.record_request_log(db=db, request_id=request_id, requested_model=payload.model, mode='AUDIO',
            status='SUCCESS' if result is not None else 'FAILED', status_code=200 if result is not None else (last_error.status_code if last_error else 503),
            latency_ms=(time.perf_counter() - started) * 1000, router_key_id=router_key.id if router_key else None,
            resolved_provider_id=resolved_model.provider_id if resolved_model else None,
            resolved_credential_id=resolved_cred.id if resolved_cred else None,
            upstream_model=resolved_model.provider_model_id if resolved_model else None, attempts=attempts,
            error_category=last_error.category.value if result is None and last_error else None,
            error_message=last_error.message if result is None and last_error else None,
            metadata_json={'endpoint': AUDIO_ENDPOINT, 'audio_bytes': len(audio), 'response_format': payload.response_format,
                           'audio_duration_seconds': result.get('duration') if isinstance(result, dict) else None,
                           'billing_unit': 'audio_seconds', 'cost_known': False},
            response_content=json.dumps(result, ensure_ascii=False) if result is not None else None)
        if result is None:
            raise last_error or RouterException('No eligible audio credentials', ErrorCategory.MODEL_NOT_FOUND, status_code=503)
        return result
