"""Thin adapter to freebuff2api-wokers; upstream protocol stays in worker.js."""
from __future__ import annotations

import asyncio
from contextlib import aclosing, suppress
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
from urllib.parse import urlsplit
import uuid


def _worker():
    """One writer per pool, private environment, stop children on parent-pipe EOF."""
    import fcntl
    os.umask(0o077)
    cfg = json.loads(sys.stdin.readline())
    root = Path(cfg['root'])
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    threading.Thread(target=lambda: (sys.stdin.read(), stop.set()), daemon=True).start()
    process = None
    with (root / 'owner.lock').open('a') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # An account must not silently migrate to a different egress after an edit.
            pin = hashlib.sha256(json.dumps(cfg['proxy']).encode()).hexdigest()
            pin_file = root / 'egress.json'
            credentials = root / 'data' / 'credentials'
            credentials.mkdir(parents=True, exist_ok=True)
            if pin_file.exists() and pin_file.read_text() != pin:
                flows_file = root / 'data' / 'login-flows.json'
                pending = False
                if flows_file.exists():
                    stored = json.loads(flows_file.read_text())
                    if not isinstance(stored, dict) or not isinstance(stored.get('flows'), list):
                        raise ValueError('Ambiguous login-flow state; egress migration refused')
                    for flow in stored['flows']:
                        if (not isinstance(flow, dict) or flow.get('status') not in ('pending', 'done', 'expired', 'cancelled')
                                or any(not isinstance(flow.get(key), str) or not flow[key]
                                       for key in ('id', 'loginUrl', 'fingerprintId', 'createdAt'))
                                or str(uuid.UUID(flow['id'])) != flow['id']):
                            raise ValueError('Malformed login flow; egress migration refused')
                        pending = pending or flow['status'] == 'pending'
                if any(credentials.glob('*.json')) or pending:
                    raise ValueError('Existing account/login egress changed; use a new profile or restore its original proxy')
            pin_file.write_text(pin)

            env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'TMPDIR')}
            for key, folder in {'HOME': 'home', 'XDG_CONFIG_HOME': 'config', 'XDG_DATA_HOME': 'user-data',
                                'XDG_CACHE_HOME': 'cache', 'XDG_STATE_HOME': 'state'}.items():
                target = root / folder
                target.mkdir(exist_ok=True)
                env[key] = str(target)
            # Separate process group: watchdog survives until the owned Node exits.
            with (root / 'service.log').open('ab', buffering=0) as log:
                process = subprocess.Popen([cfg['node'], str(Path(__file__).with_name('runtime.mjs'))],
                    stdin=subprocess.PIPE, cwd=root, env=env, stdout=log, stderr=log, start_new_session=True)
                assert process.stdin is not None
                process.stdin.write((json.dumps(cfg) + '\n').encode())
                process.stdin.flush()
            while not stop.wait(.2) and process.poll() is None:
                pass
        except Exception:
            print('Freebuff supervisor failed; check private service configuration/runtime', file=sys.stderr)
        finally:
            if process is not None:
                # ponytail: POSIX process groups; use Job Objects for a Windows port.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    pass
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                if process.stdin:
                    process.stdin.close()


if __name__ == '__main__':
    _worker()
    sys.exit(0)

import httpx
from app.adapters.base import DiscoveredModelData
from app.adapters.openai import iter_chat_sse
from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.modules.base import BaseModuleAdapter, ChatStreamAccumulator, SubscriptionLimit, SubscriptionLimits, collect_chat_completion
from app.modules.loader import ModuleLoader


def _client(runtime, timeout):
    # Never apply the upstream proxy to the loopback management connection, or send cookies.
    return httpx.AsyncClient(base_url=runtime['url'], headers={'Authorization': 'Bearer ' + runtime['token']},
                             trust_env=False, follow_redirects=False, timeout=timeout)


def _error(status=502, *, replay_safe=True):
    error = normalize_upstream_error(status_code=status, response_body={'message': f'Freebuff request failed (HTTP {status})'})
    error.replay_safe = replay_safe
    return error


async def _stop(proc):
    if proc.stdin:
        proc.stdin.close()
    # EOF watchdog gracefully shuts down the exact owned group, not foreign listeners.
    try:
        await asyncio.wait_for(proc.wait(), 25)
    except TimeoutError:
        with suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        await asyncio.wait_for(proc.wait(), 25)


class FreebuffAdapter(BaseModuleAdapter):
    def __init__(self):
        previous = ModuleLoader.get_adapter('freebuff')
        self._workers = getattr(previous, '_workers', {})
        self._lock = getattr(previous, '_lock', asyncio.Lock())

    def _settings(self, ctx):
        if os.name != 'posix':
            raise RouterException('Freebuff managed runtime requires POSIX', ErrorCategory.INVALID_REQUEST)
        profile = ctx.extra_config.get('credential_id')
        instance = ctx.extra_config.get('credential_instance')
        if type(profile) is not int or profile <= 0 or not isinstance(instance, str) or not instance:
            raise RouterException('Save a Freebuff profile before connecting', ErrorCategory.INVALID_REQUEST)
        fields = ctx.credentials
        source = Path(str(fields.get('project_path') or '/home/kiril/PythonProjects/freebuff2api-wokers')).expanduser().resolve()
        # Preserve saved profiles when replacing the previous default implementation.
        if source == Path('/home/kiril/PythonProjects/freebuff-proxy'):
            source = Path('/home/kiril/PythonProjects/freebuff2api-wokers')
        if not all((source / name).is_file() for name in ('worker.js', 'package.json')):
            raise RouterException('freebuff2api-wokers checkout is missing', ErrorCategory.INVALID_REQUEST)
        if not (source / 'node_modules' / 'undici').is_dir():
            raise RouterException('Run npm ci in the freebuff2api-wokers checkout', ErrorCategory.INVALID_REQUEST)
        binaries = {}
        for key, fallback in (('node', 'node'),):
            value = fields.get(key + '_path') or fallback
            found = shutil.which(str(value))
            if not found:
                raise RouterException(f'{key} executable is missing; configure {key}_path', ErrorCategory.INVALID_REQUEST)
            binaries[key] = str(Path(found).resolve())
        timeout = fields.get('startup_timeout', 30)
        if isinstance(timeout, bool) or not re.fullmatch(r'[0-9]+', str(timeout)) or not 5 <= int(timeout) <= 120:
            raise RouterException('startup_timeout must be an integer from 5 to 120', ErrorCategory.INVALID_REQUEST)
        if ctx.proxy_url is not None:
            try:
                proxy = urlsplit(ctx.proxy_url)
                if (proxy.scheme not in ('http', 'https') or not proxy.hostname or proxy.path not in ('', '/')
                        or proxy.query or proxy.fragment or any(c.isspace() or ord(c) < 32 for c in ctx.proxy_url)
                        or proxy.port is not None and proxy.port < 1):
                    raise ValueError()
            except (ValueError, TypeError):
                raise RouterException('Freebuff requires an HTTP(S) upstream proxy; no direct fallback', ErrorCategory.INVALID_REQUEST) from None
        if not math.isfinite(ctx.timeout) or ctx.timeout <= 0:
            raise RouterException('timeout must be finite and positive', ErrorCategory.INVALID_REQUEST)
        api_base = fields.get('api_base') or 'https://www.codebuff.com'
        try:
            base = urlsplit(api_base)
            if (base.scheme not in ('http', 'https') or not base.hostname or base.username or base.password
                    or base.query or base.fragment or base.path not in ('', '/') or base.port == 0
                    or any(c.isspace() or ord(c) < 32 for c in api_base)):
                raise ValueError()
        except (ValueError, TypeError):
            raise RouterException('Invalid Freebuff upstream API origin', ErrorCategory.INVALID_REQUEST) from None
        accounts = []
        auth_token = fields.get('auth_token')
        if auth_token:
            if (not isinstance(auth_token, str) or len(auth_token) <= 8
                    or any(c.isspace() or c in ',:' for c in auth_token)):
                raise RouterException('Freebuff requires one authToken without separators', ErrorCategory.INVALID_REQUEST)
            accounts.append({'authToken': auth_token})
        return dict(binaries, source=str(source), profile=profile, instance=hashlib.sha256(instance.encode()).hexdigest(),
                    proxy=ctx.proxy_url, startup_timeout=int(timeout), apiBase=api_base.rstrip('/'),
                    accounts=accounts, engine='freebuff2api-wokers')

    async def _runtime(self, ctx):
        async with self._lock:
            if 'profile_proxy_id' in ctx.extra_config:
                from app.core.database import AsyncSessionLocal
                from app.services.proxy_service import ProxyService
                proxy_id = ctx.extra_config['profile_proxy_id']
                proxy_url = None
                if proxy_id is not None:
                    try:
                        async with AsyncSessionLocal() as db:
                            proxy_url = (await ProxyService.resolve_proxy_pool(db, [proxy_id]))[0]
                    except ValueError:
                        raise RouterException('Saved Freebuff proxy is missing or disabled; no direct fallback', ErrorCategory.INVALID_REQUEST) from None
                ctx = ctx.model_copy(update={'proxy_url': proxy_url})
            cfg = self._settings(ctx)
            current = self._workers.get(cfg['profile'])
            if current and current['process'].returncode is None and current['configuration'] == cfg:
                return current
            if current:
                await _stop(current['process'])
                self._workers.pop(cfg['profile'], None)
            base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state') / 'MyAIrouter' / 'freebuff'
            root = base / f"{cfg['profile']}-{cfg['instance']}"
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            root.chmod(0o700)
            base.chmod(0o700)
            token = secrets.token_urlsafe(32)
            env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'TMPDIR')}
            log = root / 'service.log'
            # Truncate only after acquiring pool ownership in worker; do not touch a foreign writer's log.
            offset = log.stat().st_size if log.exists() else 0
            proc = await asyncio.create_subprocess_exec(sys.executable, '-I', str(Path(__file__).resolve()),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                env=env, start_new_session=True)
            try:
                proc.stdin.write((json.dumps(dict(cfg, root=str(root), token=token)) + '\n').encode())
                await proc.stdin.drain()
                deadline = asyncio.get_running_loop().time() + cfg['startup_timeout']
                while proc.returncode is None and asyncio.get_running_loop().time() < deadline:
                    if log.exists():
                        with log.open('rb') as reader:
                            reader.seek(offset)
                            for line in reader:
                                try:
                                    item = json.loads(line)
                                except ValueError:
                                    continue
                                if not isinstance(item, dict):
                                    continue
                                port = item.get('port')
                                if item.get('msg') == 'freebuff2api listening' and type(port) is int and 0 < port <= 65535:
                                    current = dict(process=proc, url=f'http://127.0.0.1:{port}', token=token,
                                                   configuration=cfg, root=root)
                                    async with _client(current, min(ctx.timeout, 5)) as client:
                                        status = await client.get('/v1/freebuff/status')
                                        if (status.status_code != 200 or
                                                status.json().get('upstream', {}).get('pinnedEgress') is not True):
                                            raise RouterException('Freebuff checkout lacks required pinned-egress support', ErrorCategory.INVALID_REQUEST)
                                        self._workers[cfg['profile']] = current
                                        return current
                    await asyncio.sleep(.1)
                raise RouterException('Freebuff failed to start; check Node/dependencies or pinned profile egress', ErrorCategory.NETWORK_ERROR)
            except BaseException:
                cleanup = asyncio.create_task(_stop(proc))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                raise

    async def _json(self, ctx, method, path, *, mutation=False):
        runtime = await self._runtime(ctx)
        try:
            async with _client(runtime, ctx.timeout) as client:
                response = await client.request(method, path)
                if response.status_code != 200:
                    raise _error(response.status_code, replay_safe=not mutation)
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError()
                return data
        except httpx.HTTPError:
            raise RouterException('Freebuff transport failed', ErrorCategory.NETWORK_ERROR, replay_safe=not mutation) from None
        except ValueError:
            raise _error(replay_safe=not mutation) from None

    async def validate_credentials(self, ctx):
        try:
            data = await self._json(ctx, 'GET', '/v1/models')
            return True, 'freebuff2api-wokers ready; advertised models do not prove account access', len(data.get('data', []))
        except RouterException as error:
            return False, error.message, 0

    async def list_models(self, ctx):
        # Worker discovers public models; it does not query/admit account sessions here.
        data = await self._json(ctx, 'GET', '/v1/models')
        result = []
        for row in data.get('data', []):
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise _error()
            context = row.get('context_window')
            result.append(DiscoveredModelData(provider_model_id=row['id'], display_name=row.get('display_name') or row['id'],
                context_length=context if type(context) is int and context > 0 else None,
                capabilities={'chat': True, 'streaming': True, 'tools': True, 'vision': False, 'audio_input': False,
                              'audio_output': False, 'embeddings': False, 'structured_output': False,
                              'reasoning': True, 'sampling': True}))
        return result

    def _flow(self, data):
        flow = data.get('flow')
        if not isinstance(flow, dict) or flow.get('status') not in ('pending', 'done', 'expired', 'cancelled'):
            raise _error(replay_safe=False)
        try:
            if str(uuid.UUID(flow['id'])) != flow['id']:
                raise ValueError()
            url = urlsplit(flow['loginUrl'])
            if url.scheme != 'https' or url.hostname not in ('freebuff.com', 'www.freebuff.com', 'codebuff.com', 'www.codebuff.com') or url.username or url.password or url.port not in (None, 443):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise _error(replay_safe=False) from None
        # Do not forward tokens, fingerprint/device material or raw upstream errors.
        public = {key: flow.get(key) for key in ('id', 'status', 'loginUrl', 'createdAt', 'expiresAt')}
        if flow.get('error'):
            public['error'] = 'Freebuff login pending or expired; check service connection'
        return {'flow': public}

    async def login_start(self, ctx):
        return self._flow(await self._json(ctx, 'POST', '/api/accounts/login', mutation=True))

    async def login_status(self, ctx, flow_id):
        if not isinstance(flow_id, str) or str(uuid.UUID(flow_id)) != flow_id:
            raise RouterException('Invalid Freebuff login flow ID', ErrorCategory.INVALID_REQUEST)
        return self._flow(await self._json(ctx, 'GET', '/api/accounts/login/' + flow_id))

    async def login_cancel(self, ctx, flow_id):
        await self.login_status(ctx, flow_id)
        await self._json(ctx, 'POST', '/api/accounts/login/' + flow_id + '/cancel', mutation=True)
        return await self.login_status(ctx, flow_id)

    async def get_subscription_limits(self, ctx):
        data = await self._json(ctx, 'GET', '/v1/freebuff/status')
        limits = []
        for account in data.get('accounts', []):
            quota = account.get('quota') or {}
            for model, value in (quota.get('byModel') or {}).items():
                if not isinstance(value, dict):
                    continue
                def number(key):
                    raw = value.get(key)
                    return raw if type(raw) in (int, float) and math.isfinite(raw) and raw >= 0 else None
                maximum, used = number('limit'), number('recentCount')
                limits.append(SubscriptionLimit(name=f"{account.get('email') or 'Account'} · session units", model=model,
                    limit=maximum, used=used, remaining=max(0, maximum-used) if maximum is not None and used is not None else None,
                    unit='session_units', reset_at=value.get('resetAt') if isinstance(value.get('resetAt'), str) else None))
        return SubscriptionLimits(status='ok' if limits else 'unavailable', limits=limits,
                                  message='Cached Freebuff snapshot; refresh models to update quota')

    async def stream_chat(self, request, ctx):
        request.reject_unknown_parameters('Freebuff')
        payload = request.model_dump(exclude_none=True)
        payload.update(model=ctx.model_id or request.model, stream=True)
        # Ignore only a router-generated companion budget, never an explicit client option.
        if request.reasoning_effort is not None and 'thinking' not in getattr(request, '_routing_client_fields', {'thinking'}):
            payload.pop('thinking', None)
        runtime = await self._runtime(ctx)
        accumulator = ChatStreamAccumulator()
        try:
            # ponytail: one generation per profile; worker session mutations aren't concurrency-safe.
            async with asyncio.timeout(ctx.timeout), runtime.setdefault('chat_lock', asyncio.Lock()), _client(runtime, ctx.timeout) as client:
                object.__setattr__(request, '_upstream_submission_started', True)
                async with client.stream('POST', runtime['url'] + '/v1/chat/completions', json=payload) as response:
                    if response.status_code != 200:
                        if response.status_code == 403:
                            await response.aread()
                            with suppress(ValueError):
                                body = response.json()
                                error = body.get('error') if isinstance(body, dict) else None
                                if isinstance(error, dict) and error.get('code') == 'freebuff_access_blocked':
                                    reason = error.get('reason')
                                    reason = reason if reason in ('banned', 'country_blocked', 'region_locked') else 'access_blocked'
                                    raise RouterException(f'Freebuff blocked access for this account or region: {reason}',
                                        ErrorCategory.AUTH_ERROR, status_code=403, upstream_status=403, replay_safe=False)
                        if response.status_code == 410:
                            await response.aread()
                            with suppress(ValueError):
                                body = response.json()
                                error = body.get('error') if isinstance(body, dict) else None
                                code = error.get('code') if isinstance(error, dict) else error
                                if code == 'freebuff_update_required':
                                    raise RouterException('Freebuff rejected this client: freebuff_update_required; update the upstream project',
                                        ErrorCategory.UPSTREAM_5XX, status_code=502, upstream_status=410, replay_safe=False)
                        if response.status_code == 400:
                            await response.aread()
                            with suppress(ValueError):
                                body = response.json()
                                error = body.get('error') if isinstance(body, dict) else None
                                if (isinstance(error, dict) and error.get('code') == 'unsupported_parameter'
                                        and error.get('param') in type(request).model_fields):
                                    raise RouterException(f"Freebuff does not support parameter: {error['param']}",
                                        ErrorCategory.INVALID_REQUEST, status_code=400)
                        # Refusals before generation can fall back; ambiguous service failures cannot.
                        raise _error(response.status_code, replay_safe=response.status_code in (400, 401, 403, 404, 429))
                    if 'text/event-stream' not in response.headers.get('content-type', ''):
                        raise _error(replay_safe=False)
                    async with aclosing(iter_chat_sse(response, max_bytes=ChatStreamAccumulator.MAX_BYTES)) as source:
                        async for frame in source:
                            accumulator.feed(frame)
                            if accumulator.error:
                                raise _error(replay_safe=False)
                            if accumulator.done:
                                complete = accumulator.response(payload['model'], require_complete=True)
                                declared = {tool.get('function', {}).get('name') for tool in (request.tools or [])}
                                if any(call.function.name not in declared for choice in complete.choices
                                       for call in (choice.message.tool_calls or [])):
                                    raise RouterException('Freebuff returned an undeclared tool; no server execution occurred',
                                        ErrorCategory.UPSTREAM_5XX, replay_safe=False)
                            yield frame
                            if accumulator.done:
                                return
                    raise _error(replay_safe=False)
        except RouterException:
            raise
        except (ValueError, TypeError, httpx.HTTPError, TimeoutError):
            raise _error(replay_safe=False) from None

    async def chat_completions(self, request, ctx):
        return await collect_chat_completion(self.stream_chat(request, ctx), ctx.model_id or request.model, require_complete=True)

    async def _close(self, profile=None):
        async def cleanup():
            async with self._lock:
                for key, worker in list(self._workers.items()):
                    if profile is None or key == profile:
                        await _stop(worker['process'])
                        self._workers.pop(key, None)
        task = asyncio.create_task(cleanup())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise

    async def close_profile(self, credential_id):
        await self._close(credential_id)

    async def close(self):
        await self._close()
