"""Qoder's native CLI owns authentication, model selection and generation."""
import asyncio
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import tempfile
from urllib.parse import urlsplit

from app.adapters.base import DiscoveredModelData
from app.core.errors import ErrorCategory, RouterException
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext
from app.schemas.chat import ChatCompletionChoice, ChatCompletionResponse, ChatMessage, UsageInfo

MAX_AUTH_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


def egress_fingerprint(proxy_url):
    if proxy_url is not None:
        try:
            url = urlsplit(proxy_url)
            if (url.scheme not in ('http', 'https') or not url.hostname or url.path not in ('', '/')
                    or url.query or url.fragment or any(c.isspace() or ord(c) < 32 for c in proxy_url)
                    or url.port is not None and url.port < 1):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('Qoder requires an HTTP(S) proxy; no direct fallback') from None
    return hashlib.sha256(json.dumps(proxy_url).encode()).hexdigest()


def _bundle(raw):
    if not isinstance(raw, str) or len(raw) > 3 * MAX_AUTH_BYTES:
        raise ValueError("Invalid Qoder native auth bundle")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate Qoder auth key")
            result[key] = value
        return result
    try:
        data = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(data, dict) or set(data) != {"version", "user", "machine_id"} or type(data['version']) is not int or data['version'] != 1:
            raise ValueError()
        for key, bound in (("user", MAX_AUTH_BYTES), ("machine_id", 4096)):
            value = data[key]
            if not isinstance(value, str) or len(value) > 4 * bound // 3 + 4:
                raise ValueError()
            decoded = base64.b64decode(value, validate=True)
            if not decoded or len(decoded) > bound or base64.b64encode(decoded).decode() != value:
                raise ValueError()
        return data
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValueError("Invalid Qoder native auth bundle") from exc


def normalize_auth(fields: dict) -> dict:
    """One method only; api_key is a legacy PAT alias, never an access token."""
    if not isinstance(fields, dict):
        raise ValueError("Invalid Qoder credentials")
    values = {}
    for key in ("auth_json", "personal_access_token", "api_key"):
        value = fields.get(key, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError("Invalid Qoder credentials")
        values[key] = value.strip()
    if any(fields.get(k) for k in ("access_token", "refresh_token", "token", "apiKey", "api_base")):
        raise ValueError("Qoder requires a native browser bundle or personal access token")
    pat, alias, raw = values['personal_access_token'], values['api_key'], values['auth_json']
    if pat and alias and pat != alias or raw and (pat or alias):
        raise ValueError("Conflicting Qoder authentication methods")
    if raw:
        return {"auth_json": json.dumps(_bundle(raw), separators=(',', ':'), sort_keys=True)}
    if pat or alias:
        token = pat or alias
        if len(token) > 16384 or any(ord(c) < 32 for c in token):
            raise ValueError("Invalid Qoder personal access token")
        return {"personal_access_token": token}
    raise ValueError("Missing Qoder browser account or personal access token")


def native_environment(root: Path, fields: dict, proxy_url: str | None) -> dict:
    """Allowlisted environment, including for unauthenticated browser login."""
    egress_fingerprint(proxy_url)
    root = root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = {"PATH": os.defpath, "HOME": str(root / 'home'), "QODER_CONFIG_DIR": str(root / 'config'),
           "CI": "1", "BROWSER": "www-browser", "LANG": "C.UTF-8", "QODER_NO_RC": "1"}
    for name, folder in (("HOME", 'home'), ("XDG_CONFIG_HOME", 'xdg/config'),
                         ("XDG_DATA_HOME", 'xdg/data'), ("XDG_CACHE_HOME", 'xdg/cache'),
                         ("XDG_STATE_HOME", 'xdg/state'), ("TMPDIR", 'tmp'),
                         ("QODER_CONFIG_DIR", 'config')):
        path = root / folder
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        env[name] = str(path)
    if fields:
        auth = normalize_auth(fields)
        if 'personal_access_token' in auth:
            env['QODER_PERSONAL_ACCESS_TOKEN'] = auth['personal_access_token']
    if proxy_url:
        env.update(HTTPS_PROXY=proxy_url, HTTP_PROXY=proxy_url, ALL_PROXY=proxy_url,
                   https_proxy=proxy_url, http_proxy=proxy_url, all_proxy=proxy_url)
    return env


def qoder_executable(cli_path: str | None = None) -> str:
    found = cli_path or shutil.which('qodercli')
    if not found or not Path(found).is_file() or not os.access(found, os.X_OK):
        raise ValueError("Qoder CLI executable is not installed")
    return str(Path(found).resolve())


def read_native_auth(root: Path) -> str:
    """Read only private native files created inside the supplied login root."""
    root = root.resolve()
    directory = root / 'config' / '.auth'
    for path in (root / 'config', directory):
        if path.is_symlink() or not path.is_dir():
            raise ValueError("Invalid Qoder native auth directory")
    data = {"version": 1}
    for name, bound in (("user", MAX_AUTH_BYTES), ("machine_id", 4096)):
        fd = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or not 0 < info.st_size <= bound:
                raise ValueError("Qoder native auth files must be private and bounded")
            with os.fdopen(fd, 'rb', closefd=False) as file:
                value = file.read(bound + 1)
            if not value or len(value) > bound:
                raise ValueError("Invalid Qoder native auth file")
            data[name] = base64.b64encode(value).decode()
        finally:
            os.close(fd)
    return json.dumps(data, separators=(',', ':'), sort_keys=True)


async def stop_process(proc, *, drain_output=True):
    """Call only for owned processes started with start_new_session=True."""
    async def drain(pipe):
        if pipe:
            while await pipe.read(65536):
                pass
    drains = [asyncio.create_task(drain(pipe)) for pipe in (proc.stdout, proc.stderr)] if drain_output else []
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), 2)
    except asyncio.TimeoutError:
        pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
        await asyncio.gather(*drains)


def _invalid(message):
    return RouterException(message, ErrorCategory.INVALID_REQUEST, status_code=400)


def _upstream(message):
    return RouterException(message, ErrorCategory.UPSTREAM_5XX, status_code=502, replay_safe=False)


class QoderAdapter(BaseModuleAdapter):
    def __init__(self):
        from app.modules.loader import ModuleLoader
        previous = ModuleLoader.get_adapter('qoder')
        if getattr(previous, '_closed', False):
            previous = None
        self._locks = getattr(previous, '_locks', {})
        self._auth = getattr(previous, '_auth', {})
        self._processes = getattr(previous, '_processes', {})
        self._epochs = getattr(previous, '_epochs', {})
        self._closed = False

    async def close(self):
        self._closed = True
        # In-flight requests still own their pipe readers; their finally blocks drain.
        await asyncio.gather(*(stop_process(p, drain_output=False) for p in tuple(self._processes)))
        self._auth.clear()

    async def close_profile(self, credential_id):
        # Keep its lock so a queued request cannot bypass an in-flight refresh.
        key = str(credential_id)
        self._epochs[key] = self._epochs.get(key, 0) + 1
        self._auth.pop(key, None)
        await asyncio.gather(*(stop_process(p, drain_output=False) for p, profile in tuple(self._processes.items()) if profile == key))

    async def _run(self, ctx: ModuleExecutionContext, options, prompt=None, system=None):
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
                    raise _invalid('Saved Qoder proxy is missing or disabled; no direct fallback') from None
            ctx = ctx.model_copy(update={'proxy_url': proxy_url})
        pin = ctx.credentials.get('qoder_egress_pin')
        try:
            current_pin = egress_fingerprint(ctx.proxy_url)
        except ValueError as exc:
            raise _invalid(str(exc)) from None
        if 'qoder_egress_pin' in ctx.credentials and pin != current_pin:
            raise _invalid('Qoder account egress changed; restore its proxy or authorize a new profile')
        try:
            auth = normalize_auth(ctx.credentials)
            executable = qoder_executable(ctx.credentials.get('cli_path'))
        except ValueError as exc:
            raise _invalid(str(exc)) from exc
        source = auth.get('auth_json')
        identity = {'machine_id': json.loads(source)['machine_id']} if source else auth
        key = str(ctx.extra_config.get('credential_id') or hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest())
        epoch = self._epochs.get(key, 0)
        async with self._locks.setdefault(key, asyncio.Lock()):
            if self._closed or epoch != self._epochs.get(key, 0):
                raise _upstream("Qoder CLI adapter is closed")
            cached = self._auth.get(key)
            if cached and source not in (cached['source'], cached['auth_json']):
                cached = None
                self._auth.pop(key, None)
            if cached:
                auth = {'auth_json': cached['auth_json']}
            persist = ctx.extra_config.get('persist_credentials')
            if cached and cached.get('pending') and persist:
                await persist({'auth_json': cached['auth_json']})
                cached['pending'] = False
            scratch = Path(os.environ.get('TMPDIR') or Path.home() / '.hermes/cache/scratch')
            scratch.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='myairouter-qoder-', dir=scratch) as folder:
                root = Path(folder)
                try:
                    env = native_environment(root, auth, ctx.proxy_url)
                except ValueError as exc:
                    raise _invalid(str(exc)) from None
                cwd = root / 'cwd'
                cwd.mkdir(mode=0o700)
                if 'auth_json' in auth:
                    directory = root / 'config/.auth'
                    directory.mkdir(mode=0o700)
                    bundle = _bundle(auth['auth_json'])
                    for name in ('user', 'machine_id'):
                        path = directory / name
                        with path.open('xb') as file:
                            os.chmod(path, 0o600)
                            file.write(base64.b64decode(bundle[name], validate=True))
                args = [executable, '--config-dir', str(root / 'config'), '--cwd', str(cwd),
                        '--setting-sources', '', '--settings', '{}', '--tools', '',
                        '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                        '--permission-mode', 'dont_ask', '--headless-fast-hooks', '--disable-builtin-skills', *options]
                if system:
                    path = root / 'system.txt'
                    path.write_text(system)
                    path.chmod(0o600)
                    args += ['--system-prompt-file', str(path)]
                proc = None
                async def execute():
                    nonlocal proc
                    proc = await asyncio.create_subprocess_exec(*args, cwd=cwd, env=env,
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE, start_new_session=True)
                    self._processes[proc] = key
                    if self._closed or epoch != self._epochs.get(key, 0):
                        raise _upstream('Qoder CLI profile was closed')
                    async def read(pipe):
                        chunks, size = [], 0
                        while chunk := await pipe.read(65536):
                            size += len(chunk)
                            if size > MAX_OUTPUT_BYTES:
                                raise _upstream("Qoder CLI output exceeds 8 MiB")
                            chunks.append(chunk)
                        return b''.join(chunks)
                    async def write():
                        if prompt is not None:
                            proc.stdin.write(prompt.encode())
                            await proc.stdin.drain()
                        proc.stdin.close()
                    tasks = [asyncio.create_task(read(proc.stdout)), asyncio.create_task(read(proc.stderr)), asyncio.create_task(write())]
                    try:
                        output, _, _ = await asyncio.gather(*tasks)
                        await proc.wait()
                        if proc.returncode:
                            # CLI stderr can contain credentials/URLs: never propagate it.
                            raise _upstream("Qoder CLI failed; check account authentication and CLI installation")
                        return output.decode('utf-8')
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                try:
                    try:
                        return await asyncio.wait_for(execute(), ctx.timeout or 60)
                    except asyncio.TimeoutError as exc:
                        raise RouterException("Qoder CLI timed out", ErrorCategory.TIMEOUT, status_code=504, replay_safe=False) from exc
                    except (OSError, UnicodeError) as exc:
                        raise _upstream("Qoder CLI could not complete the request") from exc
                finally:
                    async def cleanup():
                        if proc:
                            await stop_process(proc)
                            self._processes.pop(proc, None)
                        if source and not self._closed and epoch == self._epochs.get(key, 0):
                            # Retain rotated opaque data before persistence; stale queued contexts never replay it.
                            try:
                                rotated = read_native_auth(root)
                            except (ValueError, OSError):
                                self._auth.pop(key, None)
                                raise _upstream("Qoder native account state is unavailable")
                            if rotated != auth['auth_json']:
                                current = {'source': cached['source'] if cached else source,
                                           'auth_json': rotated, 'pending': True}
                                self._auth[key] = current
                                ctx.credentials['auth_json'] = rotated
                                if persist:
                                    await persist({'auth_json': rotated})
                                    current['pending'] = False
                    task = asyncio.create_task(cleanup())
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        await task
                        raise

    async def list_models(self, ctx):
        output = await self._run(ctx, ['--list-models'])
        lines = output.strip().splitlines()
        if not lines or lines[0] != 'MODEL':
            raise _upstream("Unsupported Qoder CLI model-list output")
        discovered, seen = [], set()
        # Native 1.1.68 prints system display names; --model accepts those names.
        for line in lines[1:]:
            name = line.strip()
            if not name:
                continue
            match = re.fullmatch(r'(.+) \(([^()]+)\)', name)
            model = match[2] if match else name
            if '\u2026' in model:  # Native truncates custom keys at 40 chars: not a usable identifier.
                continue
            if model in seen:
                continue
            seen.add(model)
            discovered.append(DiscoveredModelData(provider_model_id=model,
                display_name=match[1] if match else name, context_length=None, max_output_tokens=None,
                capabilities={'chat': True, 'streaming': True, 'vision': False, 'tools': False, 'reasoning': False}))
        return discovered

    async def validate_credentials(self, ctx):
        try:
            models = await self.list_models(ctx)
            return True, 'Qoder CLI credentials are valid', len(models)
        except Exception:
            return False, 'Qoder CLI credential validation failed', 0

    def _chat_input(self, request, model_id=None):
        request.reject_unknown_parameters('Qoder CLI')
        for name in ('temperature', 'top_p', 'stop', 'presence_penalty', 'frequency_penalty',
                     'logit_bias', 'seed', 'response_format', 'reasoning_effort', 'reasoning', 'thinking',
                     'tools', 'tool_choice', 'parallel_tool_calls', 'prompt_cache_key'):
            if getattr(request, name) is not None:
                raise _invalid(f'Qoder CLI does not support parameter: {name}')
        if request.n not in (None, 1):
            raise _invalid('Qoder CLI supports one completion')
        if request.stream_options and set(request.stream_options) - {'include_usage'}:
            raise _invalid('Unsupported Qoder stream option')
        system, turns = [], []
        for message in request.messages:
            if message.role in ('tool', 'function') or message.tool_calls or message.tool_call_id or message.reasoning_details or message.reasoning_content:
                raise _invalid('Qoder CLI chat bridge does not support tool or reasoning history')
            content = message.content
            if isinstance(content, list):
                if any(not isinstance(b, dict) or set(b) - {'type', 'text'} or b.get('type') != 'text' or not isinstance(b.get('text'), str) for b in content):
                    raise _invalid('Qoder CLI chat bridge supports text only')
                content = '\n'.join(b['text'] for b in content)
            if not isinstance(content, str):
                raise _invalid('Qoder CLI messages require text')
            if message.role in ('system', 'developer'):
                system.append(content)
            else:
                turns.append({'role': message.role, 'content': content})
        if not turns or turns[-1]['role'] != 'user':
            raise _invalid('Qoder CLI requires a final user message')
        # ponytail: one JSON transcript, not persisted native session history.
        # Escape @ so native file/peer-reference expansion cannot read relay paths.
        # The prefix also prevents user content from becoming a CLI slash command.
        prompt = 'Continue this conversation (JSON):\n' + json.dumps(turns, ensure_ascii=False).replace('@', '\\u0040')
        system = '\n\n'.join(system)
        if len((prompt + system).encode()) > MAX_OUTPUT_BYTES:
            raise _invalid('Qoder CLI input exceeds 8 MiB')
        limit = request.get_effective_max_tokens()
        if limit is not None and limit <= 0:
            raise _invalid('max_tokens must be positive')
        model = model_id if model_id is not None else request.model.removeprefix('qoder/')
        if not model or model.startswith('-') or len(model) > 512 or any(ord(c) < 32 for c in model):
            raise _invalid('Invalid Qoder model')
        options = ['--print', '--output-format', 'json', '--no-session-persistence',
                   '--max-turns', '1', '--max-model-request-retries', '0', '--model', model]
        if limit is not None:
            options += ['--max-output-tokens', str(limit)]
        return options, prompt, system

    async def chat_completions(self, request, ctx):
        options, prompt, system = self._chat_input(request, ctx.model_id or None)
        output = await self._run(ctx, options, prompt, system)
        try:
            result = json.loads(output)
            if not isinstance(result, dict) or result.get('type') != 'result' or result.get('subtype') != 'success' or result.get('is_error') is not False or not isinstance(result.get('result'), str):
                raise ValueError()
            if result.get('permission_denials') or result.get('terminal_reason', 'completed') != 'completed':
                raise ValueError()
            reason = result.get('stop_reason')
            if reason not in (None, 'end_turn', 'stop_sequence', 'max_tokens'):
                raise ValueError()
            usage = result.get('usage')
            converted = None
            if isinstance(usage, dict) and 'input_tokens' in usage and 'output_tokens' in usage:
                counts = [usage.get(k, 0) for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')]
                if any(type(n) is not int or n < 0 for n in counts):
                    raise ValueError()
                incoming, outgoing = sum(counts[:3]), counts[3]
                converted = UsageInfo(prompt_tokens=incoming, completion_tokens=outgoing, total_tokens=incoming + outgoing)
            return ChatCompletionResponse(model=request.model, usage=converted, choices=[ChatCompletionChoice(
                message=ChatMessage(role='assistant', content=result['result']),
                finish_reason='length' if reason == 'max_tokens' else 'stop')])
        except (ValueError, TypeError, KeyError) as exc:
            raise _upstream('Qoder CLI did not return a successful text completion') from exc

    async def stream_chat(self, request, ctx):
        # ponytail: buffered SSE until native success; incremental stream-json when first-token latency matters.
        response = await self.chat_completions(request, ctx)
        common = {'id': response.id, 'object': 'chat.completion.chunk', 'created': response.created, 'model': response.model}
        yield 'data: ' + json.dumps({**common, 'choices': [{'index': 0, 'delta': {
            'role': 'assistant', 'content': response.choices[0].message.content}, 'finish_reason': None}]}) + '\n\n'
        terminal = {**common, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': response.choices[0].finish_reason}]}
        if response.usage and (request.stream_options or {}).get('include_usage'):
            terminal['usage'] = response.usage.model_dump(exclude_none=True)
        yield 'data: ' + json.dumps(terminal) + '\n\n'
        yield 'data: [DONE]\n\n'
