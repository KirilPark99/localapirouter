import json
from contextlib import aclosing
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from app.adapters.base import BaseProviderAdapter, DiscoveredModelData
from app.modules.base import ModuleExecutionContext
from app.modules.loader import ModuleLoader
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from app.core.errors import RouterException


class CustomModuleAdapter(BaseProviderAdapter):
    """
    Adapter bridge connecting MyAIrouter's routing engine to custom user modules in `backend/modules/`.
    """

    def _resolve_context(
        self,
        api_key: str,
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
        model_id: str = "",
    ) -> Tuple[Any, ModuleExecutionContext]:
        module_id = configuration.get("module_id")
        if not module_id:
            raise RouterException("Custom module error: missing module_id in configuration")

        adapter = ModuleLoader.get_adapter(module_id)
        if not adapter:
            ModuleLoader.scan_modules()
            adapter = ModuleLoader.get_adapter(module_id)
        if not adapter:
            raise RouterException(f"Custom module '{module_id}' is not loaded or has failed initialization")

        # Build credentials dict: merge decrypted metadata_json and api_key
        credentials: Dict[str, Any] = {}
        cred_metadata = configuration.get("credential_metadata") or {}
        if isinstance(cred_metadata, dict):
            credentials.update(cred_metadata)

        # If api_key contains JSON (e.g. encrypted dict of multiple secret fields), parse it
        if api_key:
            clean_k = api_key.strip()
            if clean_k.startswith("{") and clean_k.endswith("}"):
                try:
                    parsed = json.loads(clean_k)
                    if isinstance(parsed, dict):
                        credentials.update(parsed)
                except Exception:
                    credentials["api_key"] = clean_k
            else:
                credentials["api_key"] = clean_k

        ctx = ModuleExecutionContext(
            credentials=credentials,
            proxy_url=proxy_url,
            model_id=model_id,
            timeout=timeout,
            extra_config=configuration,
        )
        return adapter, ctx

    async def list_models(
        self,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[DiscoveredModelData]:
        adapter, ctx = self._resolve_context(api_key, configuration, proxy_url, timeout)
        return await adapter.list_models(ctx)

    async def get_subscription_limits(
        self,
        api_key: str,
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        adapter, ctx = self._resolve_context(api_key, configuration, proxy_url, timeout)
        return await adapter.get_subscription_limits(ctx)

    async def reset_subscription_limits(self, api_key: str, configuration: Dict[str, Any],
                                        redeem_request_id: str, proxy_url: Optional[str] = None):
        if configuration.get("module_id") != "codex_cli":
            raise ValueError("Subscription reset is supported only for Codex CLI")
        adapter, ctx = self._resolve_context(api_key, configuration, proxy_url, 10.0)
        return await adapter.reset_subscription_limits(ctx, redeem_request_id)

    async def validate_credentials(
        self,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 15.0,
    ) -> Tuple[bool, str, int]:
        adapter, ctx = self._resolve_context(api_key, configuration, proxy_url, timeout)
        return await adapter.validate_credentials(ctx)

    async def chat_completions(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        request: ChatCompletionRequest,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> ChatCompletionResponse:
        adapter, ctx = self._resolve_context(api_key, configuration, proxy_url, timeout, model_id)
        return await adapter.chat_completions(request, ctx)

    async def stream_chat(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        request: ChatCompletionRequest,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> AsyncGenerator[str, None]:
        adapter, ctx = self._resolve_context(api_key, configuration, proxy_url, timeout, model_id)
        async with aclosing(adapter.stream_chat(request, ctx)) as source:
            async for chunk in source:
                yield chunk

    def normalize_error(
        self,
        status_code: Optional[int] = None,
        response_body: Optional[Any] = None,
        exception: Optional[Exception] = None,
        retry_after: Optional[float] = None,
    ) -> RouterException:
        if isinstance(exception, RouterException):
            return exception
        from app.core.errors import ErrorCategory
        if status_code is not None:
            return super().normalize_error(status_code, response_body, exception, retry_after)
        err_msg = str(exception or response_body or "")
        if "ERR_RATE_LIMIT" in err_msg or "429" in err_msg or status_code == 429:
            if "Arena" in err_msg:
                msg = f"Превышен лимит запросов LMSYS Chatbot Arena (HTTP 429): {err_msg}. Подождите немного или смените IP/прокси."
            elif "ERR_RATE_LIMIT" in err_msg or "DuckDuckGo" in err_msg:
                msg = "Превышен лимит запросов DuckDuckGo AI Chat (HTTP 429). Рекомендуется привязать прокси к профилю DuckDuckGo в админ-панели или подождать 30-60 секунд."
            else:
                msg = f"Превышен лимит запросов (HTTP 429): {err_msg}"
            return RouterException(
                msg,
                ErrorCategory.RATE_LIMIT,
                status_code=429,
                retry_after=retry_after or 30.0,
            )
        if "temporarily-unavailable" in err_msg or "temporarily_unavailable" in err_msg:
            return RouterException(
                "Доступ к Notion AI временно приостановлен Notion (temporarily-unavailable). На бесплатном тарифе или при исчерпании квоты воркспейса Notion временно ограничивает генерацию (6-часовое скользящее окно либо требуется платная подписка Notion AI).",
                ErrorCategory.RATE_LIMIT,
                status_code=429,
                retry_after=retry_after or 60.0,
            )
        if "ERR_MODEL_RESTRICTED" in err_msg:
            return RouterException(
                err_msg if "доступна только по платной подписке" in err_msg else "Запрошенная модель ограничена и требует платной подписки DuckDuckGo Pro.",
                ErrorCategory.AUTH_ERROR,
                status_code=403,
            )
        if "FRONTEND_CAPTCHA_REQUIRED" in err_msg:
            return RouterException(
                err_msg,
                ErrorCategory.AUTH_ERROR,
                status_code=403,
            )
        if "upstream error" in err_msg.lower():
            return RouterException(
                err_msg,
                ErrorCategory.UPSTREAM_5XX,
                status_code=502,
            )
        return super().normalize_error(status_code, response_body, exception, retry_after)
