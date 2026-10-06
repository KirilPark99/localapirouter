"""MyAIrouter bridge to unmodified Lingling and the real OpenCode client."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

_CHAT_ONLY = ("This is a chat-only API session. Answer using the supplied conversation and attachments. "
              "Do not call tools, run commands, inspect local files, delegate tasks or open interactive questions. "
              "Ask any clarification as ordinary reply text. If local access is needed, explain that limitation; "
              "never claim to have executed an action. A rejected tool is unavailable: do not retry it.")


def _client_env(root: Path, continue_on_deny: bool = True) -> dict[str, str]:
    # Do not inherit API keys, user plugins, MCP servers or the router's proxy.
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TMPDIR")}
    for var, directory in {"HOME": "home", "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                           "XDG_STATE_HOME": "state", "XDG_CACHE_HOME": "cache"}.items():
        path = root / directory
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        env[var] = str(path)
    env.update({"OPENCODE_TEST_HOME": env["HOME"], "OPENCODE_AUTH_CONTENT": "{}",
                "OPENCODE_PURE": "true", "OPENCODE_DISABLE_AUTOUPDATE": "true",
                "OPENCODE_DISABLE_MODELS_FETCH": "true", "OPENCODE_DISABLE_PROJECT_CONFIG": "true",
                "OPENCODE_DISABLE_DEFAULT_PLUGINS": "true", "OPENCODE_DISABLE_EXTERNAL_SKILLS": "true",
                "OPENCODE_DISABLE_CLAUDE_CODE": "true", "OPENCODE_DISABLE_SHARE": "true",
                "OPENCODE_DISABLE_AUTOCOMPACT": "true", "OPENCODE_DISABLE_LSP_DOWNLOAD": "true"})
    catalog = Path.home() / ".cache" / "opencode" / "models.json"
    if catalog.is_file():
        env["OPENCODE_MODELS_PATH"] = str(catalog)
    config = root / "config" / "opencode" / "opencode.json"
    config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Use the genuine built-in agent. Approval is never granted by this bridge.
    # Reset persisted request limits on startup; discovery uses its own config directory.
    config.write_text(json.dumps({"enabled_providers": ["opencode"], "share": "disabled",
        "experimental": {"continue_loop_on_deny": continue_on_deny},
        "permission": "ask", "agent": {"build": {"mode": "primary", "permission": "ask"},
            "title": {"disable": True}}}), encoding="utf-8")
    config.chmod(0o600)
    return env


def _client_tools_server(path: Path) -> None:
    """Advertise client function schemas over MCP; never execute their operations."""
    tools = json.loads(path.read_text())
    names = {tool["name"] for tool in tools}
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                raise ValueError("Invalid JSON-RPC request")
            if "id" not in request:
                continue
            method = request.get("method")
            params = request.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("MCP params must be an object")
            response = {"jsonrpc": "2.0", "id": request["id"]}
            if method == "initialize":
                response["result"] = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                    "serverInfo": {"name": "MyAIrouter client tools", "version": "1.0"}}
            elif method == "tools/list":
                response["result"] = {"tools": tools}
            elif method == "tools/call" and params.get("name") in names:
                response["result"] = {"isError": True, "content": [{"type": "text",
                    "text": "This function is executed by the API client, never by OpenCode. Wait for the client result."}]}
            elif method == "ping":
                response["result"] = {}
            else:
                response["error"] = {"code": -32602 if method == "tools/call" else -32601, "message": "Unknown tool or method"}
        except (ValueError, TypeError, KeyError):
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                        "error": {"code": -32600, "message": "Invalid JSON-RPC request"}}
        print(json.dumps(response, ensure_ascii=False), flush=True)


def _owned_lane_running(lane) -> bool:
    return lane.process is not None and lane.process.poll() is None


def _worker() -> None:
    """Own all blocking Lingling threads and child processes outside Uvicorn."""
    import fcntl
    import urllib.request
    from lingling.health import HealthDaemon
    from lingling.lanes import TorManager
    from lingling.mitm import CertShop, TunnelPool
    from lingling.proof import make_emitter, DONE
    from lingling.relay import Relay

    os.umask(0o077)
    cfg = json.loads(sys.stdin.readline())
    root = Path(cfg["root"])
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    # Parent death/closed pipe must also close this isolated kitchen.
    threading.Thread(target=lambda: (sys.stdin.read(), stop.set()), daemon=True).start()
    owner = (root / "owner.lock").open("a")
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    emitter = make_emitter(root / "proof.log")
    manager = daemon = relay = client = None
    try:
        tools = root / "tools"
        tools.mkdir(exist_ok=True, mode=0o700)
        for name in ("geoip", "geoip6"):
            src = Path("/usr/share/tor") / name
            if src.is_file() and not (tools / name).exists():
                shutil.copyfile(src, tools / name)
        manager = TorManager(root, count=cfg["lanes"], tor_exe=cfg["tor_path"],
            exit_countries=cfg["countries"], fallback_countries=cfg["fallback_countries"],
            preferred_countries=cfg["preferred_countries"], boot_timeout=30, prune_orphans=False)
        # The original library also accepts foreign SOCKS listeners as "running".
        for lane in manager.lanes:
            lane.running = lambda lane=lane: _owned_lane_running(lane)
        if manager._geoip_path() is None:
            raise RuntimeError("Tor GeoIP database is missing; install the system Tor data files")
        error = manager.setup_lanes()
        if error:
            raise RuntimeError(error)
        daemon = HealthDaemon(manager, event=emitter)
        first = manager.lanes[0]
        manager.start_lanes([first])
        deadline = time.monotonic() + cfg["startup_timeout"]
        # A listening SOCKS port is NOT bootstrap readiness. Never go direct.
        while not stop.is_set() and time.monotonic() < deadline:
            if not first.running() and not first.healing:
                daemon.check_once()
            if manager.lane_bootstrap_pct(first) >= 100:
                code = daemon.reachable(first, probe_timeout=8)
                if code in (200, 403):
                    first.healthy, first.asked, first.probe_code = True, True, code
                    break
                if code == 429:
                    daemon.on_refused(first, code)
            stop.wait(1)
        else:
            raise RuntimeError("Lingling Tor startup timed out or was cancelled; direct traffic is disabled")
        daemon.start()
        relay = Relay(manager, event=emitter)
        relay.cert_shop = CertShop(root / "mitm")
        relay.tunnels = TunnelPool()
        port = relay.start()
        threading.Thread(target=manager.start_lanes, args=(manager.lanes[1:],), daemon=True).start()
        env = _client_env(root, cfg.get("continue_on_deny", True))
        for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            env[var] = f"http://127.0.0.1:{port}"
        env.update({"NO_PROXY": "localhost,127.0.0.1", "no_proxy": "localhost,127.0.0.1",
                    "NODE_EXTRA_CA_CERTS": str(relay.cert_shop.ca_pem_path),
                    "OPENCODE_SERVER_PASSWORD": cfg["password"]})
        workspace = root / "workspace"
        workspace.mkdir(exist_ok=True, mode=0o700)
        with (root / "opencode.log").open("ab", buffering=0) as log:
            client = subprocess.Popen([cfg["opencode_path"], "--pure", "serve", "--hostname", "127.0.0.1", "--port", "0"],
                                      cwd=workspace, env=env, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        while not stop.is_set() and client.poll() is None and time.monotonic() < deadline:
            matches = re.findall(r"http://127\.0\.0\.1:\d+", (root / "opencode.log").read_text(errors="replace"))
            if matches:
                url = matches[-1]
                auth = base64.b64encode(("opencode:" + cfg["password"]).encode()).decode()
                try:
                    req = urllib.request.Request(url + "/global/health", headers={"Authorization": "Basic " + auth})
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        if json.load(resp).get("healthy") is True:
                            print(json.dumps({"url": url, "tor": True}), flush=True)
                            break
                except (OSError, ValueError):
                    pass
            stop.wait(.2)
        else:
            raise RuntimeError("The isolated OpenCode server did not become ready")
        while not stop.wait(.5):
            if client.poll() is not None:
                raise RuntimeError("OpenCode server exited")
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), flush=True)
        raise
    finally:
        if client is not None and client.poll() is None:
            client.terminate()
            try:
                client.wait(timeout=5)
            except subprocess.TimeoutExpired:
                client.kill()
                client.wait(timeout=5)
        if daemon:
            daemon.stop()
        if relay:
            relay.stop()
        if manager:
            manager.stop_all()
        emitter(DONE)
        emitter.close()
        owner.close()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--client-tools":
        _client_tools_server(Path(sys.argv[2]))
    else:
        _worker()
    sys.exit(0)

from app.adapters.base import DiscoveredModelData
from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext, collect_chat_completion
from app.modules.loader import ModuleLoader
from app.schemas.chat import ChatCompletionRequest
import httpx


async def _stop_process(proc) -> None:
    # ponytail: POSIX-owned process groups; use Windows Job Objects when porting.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), 15)
    except asyncio.TimeoutError:
        pass
    # Lingling's daemon threads cannot be joined reliably; their worker exits here.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await proc.wait()
    if proc.stdin:
        proc.stdin.close()


def _parse_models(text: str) -> list[dict]:
    models, pos = [], 0
    decoder = json.JSONDecoder()
    while match := re.search(r"(?m)^opencode/[^\n]+\n(?=\{)", text[pos:]):
        start = pos + match.end()
        item, used = decoder.raw_decode(text[start:])
        pos = start + used
        if (isinstance(item, dict) and item.get("providerID") == "opencode" and
                item.get("status") != "deprecated" and item.get("cost", {}).get("input") == 0 and
                item.get("cost", {}).get("output") == 0):
            models.append(item)
    if not models:
        raise RouterException("OpenCode returned no available free models", ErrorCategory.MODEL_NOT_FOUND)
    return models


class LinglingAdapter(BaseModuleAdapter):
    def __init__(self):
        # Implicit rescans must not orphan a previous adapter's running workers.
        previous = ModuleLoader.get_adapter("lingling")
        self._workers = getattr(previous, "_workers", {})
        self._startup_lock = getattr(previous, "_startup_lock", asyncio.Lock())

    def _settings(self, ctx: ModuleExecutionContext) -> dict:
        if os.name != "posix":
            raise RouterException("Lingling host integration currently requires POSIX process ownership", ErrorCategory.INVALID_REQUEST)
        if ctx.proxy_url:
            raise RouterException("Lingling manages Tor itself; remove the ordinary profile proxy", ErrorCategory.INVALID_REQUEST)
        fields = ctx.credentials
        source = Path(str(fields.get("project_path") or Path.home() / "PythonProjects" / "lingling")).expanduser().resolve()
        if not all((source / "lingling" / name).is_file() for name in ("__init__.py", "lanes.py", "relay.py", "mitm.py")):
            raise RouterException("Lingling source directory is missing or incomplete", ErrorCategory.INVALID_REQUEST)
        result = {"project_path": str(source)}
        for key, binary in (("opencode_path", "opencode"), ("tor_path", "tor")):
            value = str(fields.get(key) or "").strip()
            found = shutil.which(value or binary)
            if not found or not os.access(found, os.X_OK):
                raise RouterException(f"{binary} executable not found; configure {key}", ErrorCategory.INVALID_REQUEST)
            result[key] = str(Path(found).resolve())
        for key, default, lower, upper in (("lanes", 5, 1, 16), ("startup_timeout", 600, 30, 1800)):
            raw = fields.get(key)
            raw = default if raw is None or raw == "" else raw
            if isinstance(raw, bool) or not re.fullmatch(r"[0-9]+", str(raw)) or not lower <= int(raw) <= upper:
                raise RouterException(f"{key} must be an integer from {lower} to {upper}", ErrorCategory.INVALID_REQUEST)
            result[key] = int(raw)
        for key, default in (("countries", "us,de,nl,fr,ro,gb,ca,se,pl,ch"), ("fallback_countries", ""), ("preferred_countries", "")):
            value = str(fields.get(key) or default).strip()
            countries = [x.strip().lower() for x in value.split(",") if x.strip()]
            if any(not re.fullmatch(r"[a-z]{2}", x) for x in countries):
                raise RouterException(f"{key} requires comma-separated two-letter country codes", ErrorCategory.INVALID_REQUEST)
            result[key] = list(dict.fromkeys(countries))
        return result

    def _root(self, ctx, cfg) -> Path:
        identity = str(ctx.extra_config.get("credential_id") or "local")
        digest = hashlib.sha256(json.dumps([identity, cfg], sort_keys=True).encode()).hexdigest()[:24]
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "MyAIrouter" / "lingling"
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        base.chmod(0o700)
        root = base / digest
        root.mkdir(exist_ok=True, mode=0o700)
        root.chmod(0o700)
        return root

    async def list_models(self, ctx):
        cfg = self._settings(ctx)
        root = self._root(ctx, cfg)
        workspace = root / "workspace"
        workspace.mkdir(exist_ok=True, mode=0o700)
        proc = await asyncio.create_subprocess_exec(cfg["opencode_path"], "--pure", "models", "opencode", "--verbose",
            cwd=workspace, env=_client_env(root / "catalog"), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True)
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), max(1, ctx.timeout))
            if proc.returncode:
                raise RouterException("OpenCode model discovery failed", ErrorCategory.NETWORK_ERROR)
            catalog = _parse_models(stdout.decode())
        finally:
            await _stop_process(proc)
        return [DiscoveredModelData(provider_model_id=m["id"], display_name=m["name"],
            context_length=m["limit"]["context"], max_output_tokens=m["limit"]["output"],
            capabilities={"chat": True, "streaming": True, "tools": bool(m["capabilities"].get("toolcall")),
                          "vision": m["capabilities"]["input"]["image"], "reasoning": m["capabilities"]["reasoning"]}) for m in catalog]

    async def validate_credentials(self, ctx):
        try:
            import importlib.util
            if importlib.util.find_spec("stem") is None:
                return False, "Install the required stem==1.8.2 dependency in the backend environment", 0
            models = await self.list_models(ctx)
            return True, "Lingling/OpenCode configured; Tor connects on the first generation (no direct fallback)", len(models)
        except Exception as exc:
            return False, str(exc), 0

    async def _runtime(self, ctx, client_tools=False):
        cfg = self._settings(ctx)
        # A separate owned runtime prevents agent denial from racing a second model turn.
        if client_tools:
            cfg["continue_on_deny"] = False
        root = self._root(ctx, cfg)
        key = str(root)
        async with self._startup_lock:
            current = self._workers.get(key)
            if current and current["process"].returncode is None:
                return current
            if current:
                await _stop_process(current["process"])
                self._workers.pop(key, None)
            password = uuid.uuid4().hex
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TMPDIR")}
            env.update({"PYTHONPATH": cfg["project_path"], "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
            with (root / "worker.log").open("ab", buffering=0) as log:
                proc = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()),
                    env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=log,
                    start_new_session=True)
            try:
                proc.stdin.write((json.dumps({**cfg, "root": key, "password": password}) + "\n").encode())
                await proc.stdin.drain()
                ready = json.loads(await asyncio.wait_for(proc.stdout.readline(), cfg["startup_timeout"] + 35))
                if ready.get("error"):
                    raise RouterException(ready["error"], ErrorCategory.NETWORK_ERROR)
                if ready.get("tor") is not True or not re.fullmatch(r"http://127\.0\.0\.1:[0-9]+", ready.get("url", "")):
                    raise RouterException("Lingling worker failed readiness validation", ErrorCategory.NETWORK_ERROR)
                current = {"process": proc, "url": ready["url"], "password": password, "lock": asyncio.Lock(),
                           "credential_id": ctx.extra_config.get("credential_id"), "root": root}
                self._workers[key] = current
                return current
            except BaseException:
                await _stop_process(proc)
                raise

    async def _close_workers(self, credential_id=None):
        async def stop():
            async with self._startup_lock:
                for key, worker in list(self._workers.items()):
                    if credential_id is None or worker["credential_id"] == credential_id:
                        await _stop_process(worker["process"])
                        self._workers.pop(key, None)
        cleanup = asyncio.create_task(stop())
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
            raise

    async def close(self):
        await self._close_workers()

    async def close_profile(self, credential_id):
        await self._close_workers(credential_id)

    def _client_tools(self, request):
        choice, definitions = request.tool_choice, request.tools or []
        forced = None
        if isinstance(choice, dict):
            fn = choice.get("function")
            if choice.get("type") != "function" or not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
                raise RouterException("Invalid function tool_choice", ErrorCategory.INVALID_REQUEST)
            forced = fn["name"]
        elif choice not in (None, "auto", "none", "required"):
            raise RouterException("Unsupported tool_choice", ErrorCategory.INVALID_REQUEST)
        try:
            if len(definitions) > 128 or len(json.dumps(definitions, allow_nan=False).encode()) > 8 * 1024 * 1024:
                raise ValueError()
        except (ValueError, TypeError):
            raise RouterException("Client tools must be valid JSON, at most 128 definitions and 8 MiB", ErrorCategory.INVALID_REQUEST)
        tools, names = {}, set()
        for index, definition in enumerate(definitions):
            fn = definition.get("function")
            if definition.get("type") != "function" or not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
                raise RouterException("Client tools must be function definitions", ErrorCategory.INVALID_REQUEST)
            name = fn["name"]
            schema = fn.get("parameters", {"type": "object", "properties": {}})
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) or name in names or not isinstance(schema, dict) or schema.get("type", "object") != "object" or not isinstance(fn.get("description", ""), str):
                raise RouterException("Invalid or duplicate client tool name/parameters", ErrorCategory.INVALID_REQUEST)
            names.add(name)
            if choice != "none" and (forced is None or forced == name):
                tools[f"client_t{index}"] = {**fn, "parameters": schema}
        if (forced is not None or choice == "required") and not tools:
            raise RouterException("Forced tool_choice requires a matching client tool definition", ErrorCategory.INVALID_REQUEST)
        return tools

    def _prompt(self, request):
        tools = self._client_tools(request)
        if request.n not in (None, 1) or request.stop or request.response_format or request.seed is not None or any(
                getattr(request, k) not in (None, 0, {}) for k in ("presence_penalty", "frequency_penalty", "logit_bias")):
            raise RouterException("Lingling supports one text/image completion; requested sampling/format option is unsupported", ErrorCategory.INVALID_REQUEST)
        turns = [m for m in request.messages if m.role not in ("system", "developer")]
        if not turns or turns[-1].role not in ("user", "tool", "function"):
            raise RouterException("Lingling requires a final user or client tool-result message", ErrorCategory.INVALID_REQUEST)
        if any(m.role in ("system", "developer") and not isinstance(m.content, (str, type(None))) for m in request.messages):
            raise RouterException("Lingling system/developer messages must be text", ErrorCategory.INVALID_REQUEST)
        system = "\n\n".join(m.content or "" for m in request.messages if m.role in ("system", "developer"))
        policy = _CHAT_ONLY
        if tools:
            policy = ("Client tools are available through MCP aliases. Use only those client tools for actions; "
                "never execute native OpenCode tools or interactive questions. Commands, file access and delegation "
                "must be requested through client function calls, not performed locally. "
                "The API client performs each requested action and supplies its real result on the next turn. "
                "Do not claim an action was executed before the client result. MCP alias to client function: "
                + json.dumps({alias: fn["name"] for alias, fn in tools.items()}, ensure_ascii=False))
            if request.tool_choice == "required" or isinstance(request.tool_choice, dict):
                policy += " You must request an available client tool in this response, not finish with text alone."
            if request.parallel_tool_calls is False:
                policy += " Request at most one client tool in this response."
        system = "\n\n".join(filter(None, (system, policy)))
        parts = []
        if len(turns) > 1:
            # ponytail: OpenCode SDK accepts user parts only; JSON transcript keeps history without replaying model calls.
            history = [m.model_dump(exclude_none=True) for m in turns[:-1]]
            if any(not isinstance(m.content, (str, type(None))) for m in turns[:-1]):
                raise RouterException("Images in previous turns are not supported by the OpenCode chat bridge", ErrorCategory.INVALID_REQUEST)
            parts.append({"type": "text", "text": "Previous conversation (JSON):\n" + json.dumps(history, ensure_ascii=False)})
        content = turns[-1].content
        if turns[-1].role in ("tool", "function"):
            last = turns[-1]
            if not isinstance(content, str) or (last.role == "tool" and not last.tool_call_id) or (last.role == "function" and not last.name):
                raise RouterException("Client tool results require text and a call ID or legacy function name", ErrorCategory.INVALID_REQUEST)
            parts.append({"type": "text", "text": "Continue after this client tool result (JSON):\n" + json.dumps(last.model_dump(exclude_none=True), ensure_ascii=False)})
            content = None
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content or []
        for block in blocks:
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append({"type": "text", "text": block["text"]})
            elif block.get("type") == "image_url":
                image = block.get("image_url", {})
                url = image.get("url", "") if isinstance(image, dict) else image
                match = re.fullmatch(r"data:(image/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/=]+)", url)
                if not match or len(url) > 8 * 1024 * 1024:
                    raise RouterException("Lingling images must be inline PNG/JPEG/WebP/GIF base64, not remote or local file URLs", ErrorCategory.INVALID_REQUEST)
                try:
                    base64.b64decode(match[2], validate=True)
                except ValueError as exc:
                    raise RouterException("Invalid base64 image", ErrorCategory.INVALID_REQUEST) from exc
                parts.append({"type": "file", "mime": match[1], "url": url})
            else:
                raise RouterException("Unsupported Lingling content block", ErrorCategory.INVALID_REQUEST)
        if not parts or len(json.dumps(parts).encode()) > 8 * 1024 * 1024:
            raise RouterException("Lingling prompt is empty or exceeds 8 MiB", ErrorCategory.INVALID_REQUEST)
        return {"agent": "build", "system": system, "parts": parts}

    async def chat_completions(self, request, ctx):
        return await collect_chat_completion(self.stream_chat(request, ctx), request.model, require_complete=True)

    async def stream_chat(self, request: ChatCompletionRequest, ctx: ModuleExecutionContext):
        prompt = self._prompt(request)
        tools = self._client_tools(request)
        model = ctx.model_id or request.model
        for prefix in ("module_lingling/", "lingling/", "opencode/"):
            if model.startswith(prefix):
                model = model[len(prefix):]
                break
        runtime = await self._runtime(ctx, client_tools=True) if tools else await self._runtime(ctx)
        # ponytail: one request per profile because OpenCode agent/model options are process-global.
        try:
            async with asyncio.timeout(ctx.timeout), runtime["lock"], httpx.AsyncClient(
                    base_url=runtime["url"], auth=("opencode", runtime["password"]), trust_env=False, timeout=ctx.timeout) as client:
                async def call(method, path, **kwargs):
                    resp = await client.request(method, path, **kwargs)
                    if resp.is_error:
                        raise normalize_upstream_error(status_code=resp.status_code, response_body=resp.text)
                    return resp.json() if resp.content else None
                providers = await call("GET", "/provider")
                catalog = next((p["models"] for p in providers["all"] if p["id"] == "opencode"), {})
                # Keep native limits: PATCH /config otherwise makes max_tokens sticky.
                native = runtime.setdefault("models", catalog)
                info = catalog.get(model)
                if not info or info.get("cost", {}).get("input") != 0 or info.get("cost", {}).get("output") != 0:
                    raise RouterException("Requested free OpenCode model is unavailable", ErrorCategory.MODEL_NOT_FOUND)
                if tools and not info.get("capabilities", {}).get("toolcall"):
                    raise RouterException("Selected OpenCode model does not support client tool calls", ErrorCategory.INVALID_REQUEST)
                if any(p["type"] == "file" for p in prompt["parts"]) and not info["capabilities"]["input"]["image"]:
                    raise RouterException("Selected Lingling model does not support images", ErrorCategory.INVALID_REQUEST)
                limit = dict(native.get(model, info)["limit"])
                maximum = request.get_effective_max_tokens()
                if maximum is not None:
                    if maximum < 1:
                        raise RouterException("max_tokens must be positive", ErrorCategory.INVALID_REQUEST)
                    limit["output"] = min(maximum, limit["output"])
                await call("PATCH", "/config", json={"experimental": {"continue_loop_on_deny": not bool(tools)},
                    "agent": {"build": {"temperature": request.temperature if request.temperature is not None else 1,
                    "top_p": request.top_p if request.top_p is not None else 1}}, "provider": {"opencode": {"models": {model: {"limit": limit}}}}})
                prompt["model"] = {"providerID": "opencode", "modelID": model}
                variant = request.get_effective_reasoning_effort()
                if variant:
                    if variant not in info.get("variants", {}):
                        raise RouterException("Requested reasoning variant is not supported by this OpenCode model", ErrorCategory.INVALID_REQUEST)
                    prompt["variant"] = variant
                session = await call("POST", "/session", json={"title": "MyAIrouter", "permission": [{"permission": "*", "pattern": "*", "action": "ask"}]})
                sid = session["id"]
                cid, created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
                def chunk(delta=None, finish=None, usage=None):
                    data = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": request.model,
                            "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}]}
                    if usage is not None:
                        data["usage"] = usage
                    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
                seen, types, assistant_ids, final, size = {}, {}, set(), None, 0
                completed, denials = {}, 0
                continuing = False
                tool_parts = {}
                schema = None
                try:
                    if tools:
                        effective = await call("GET", "/config") or {}
                        if effective.get("experimental", {}).get("continue_loop_on_deny") is not False:
                            raise RouterException("OpenCode agent runtime must stop on tool denial", ErrorCategory.UPSTREAM_5XX)
                        schema = runtime["root"] / "client-tools.json"
                        schema.write_text(json.dumps([{"name": alias.removeprefix("client_"),
                            "description": f"Client function {fn['name']}. " + str(fn.get("description") or ""),
                            "inputSchema": fn["parameters"]} for alias, fn in tools.items()], ensure_ascii=False))
                        schema.chmod(0o600)
                        await call("POST", "/mcp", json={"name": "client", "config": {"type": "local", "enabled": True,
                            "command": [sys.executable, str(Path(__file__).resolve()), "--client-tools", str(schema)],
                            "environment": {"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}}})
                        status = await call("GET", "/mcp") or {}
                        if status.get("client", {}).get("status") != "connected":
                            raise RouterException("OpenCode could not register client tool schemas", ErrorCategory.UPSTREAM_5XX)
                    async with client.stream("GET", "/event") as response:
                        response.raise_for_status()
                        await call("POST", f"/session/{sid}/prompt_async", json=prompt)
                        yield chunk({"role": "assistant"})
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            event = json.loads(line[5:])
                            props = event.get("properties") or {}
                            if (props.get("sessionID") or (props.get("info") or {}).get("sessionID") or (props.get("part") or {}).get("sessionID")) != sid:
                                continue
                            kind = event.get("type")
                            if kind in ("permission.asked", "question.asked"):
                                request_id = props.get("id")
                                prefix = "per" if kind == "permission.asked" else "que"
                                if not isinstance(request_id, str) or not re.fullmatch(prefix + r"[A-Za-z0-9_-]{1,128}", request_id):
                                    raise RouterException("OpenCode sent an invalid internal request ID", ErrorCategory.UPSTREAM_5XX)
                                # ponytail: three refusals per request; abort persistent tool/question loops.
                                external = kind == "permission.asked" and props.get("permission") in tools
                                denials += not external
                                if denials > 3:
                                    raise RouterException("OpenCode repeatedly requested unavailable tools/questions instead of a chat-only answer", ErrorCategory.UPSTREAM_5XX)
                                if kind == "permission.asked":
                                    # Rejecting one call may already have cancelled parallel pending asks.
                                    # Feedback changes OpenCode's rejection error type and bypasses stop-on-deny.
                                    denial = {"reply": "reject"} if tools else {"reply": "reject", "message": _CHAT_ONLY}
                                    reply = await client.post(f"/permission/{request_id}/reply", json=denial)
                                    if reply.is_error and not (external and reply.status_code == 404):
                                        raise normalize_upstream_error(status_code=reply.status_code, response_body=reply.text)
                                else:
                                    await call("POST", f"/question/{request_id}/reject")
                                continue
                            if kind == "session.error":
                                err = props.get("error") or {}
                                data = err.get("data") or {}
                                raise normalize_upstream_error(status_code=data.get("statusCode") or 502,
                                                               response_body=data.get("message") or "OpenCode generation failed")
                            if kind == "message.updated":
                                msg = props.get("info") or {}
                                if msg.get("role") == "assistant":
                                    assistant_ids.add(msg["id"])
                                    if msg["id"] not in completed:
                                        continuing = False
                                    if msg.get("error"):
                                        err = msg["error"].get("data") or {}
                                        raise normalize_upstream_error(status_code=err.get("statusCode") or 502, response_body=err.get("message") or "OpenCode generation failed")
                                    if msg.get("time", {}).get("completed"):
                                        final = msg
                                        completed[msg["id"]] = msg
                            part = props.get("part") or {}
                            if kind == "message.part.updated" and part.get("messageID") in assistant_ids and part.get("type") == "tool" and part.get("tool") in tools:
                                state = part.get("state") or {}
                                if state.get("status") in ("running", "error", "completed"):
                                    args, call_id = state.get("input"), part.get("callID")
                                    if not isinstance(args, dict) or not isinstance(call_id, str) or not call_id or len(call_id) > 256:
                                        raise RouterException("OpenCode sent invalid client tool arguments/ID", ErrorCategory.UPSTREAM_5XX)
                                    try:
                                        arguments = json.dumps(args, ensure_ascii=False, allow_nan=False)
                                    except (ValueError, TypeError) as exc:
                                        raise RouterException("OpenCode sent non-JSON client tool arguments", ErrorCategory.UPSTREAM_5XX) from exc
                                    if len(arguments.encode()) > 8 * 1024 * 1024:
                                        raise RouterException("Client tool arguments exceed 8 MiB", ErrorCategory.UPSTREAM_5XX)
                                    item = {"id": call_id, "type": "function", "function": {"name": tools[part["tool"]]["name"], "arguments": arguments}}
                                    key = (part["messageID"], call_id)
                                    if key in tool_parts and tool_parts[key] != item:
                                        raise RouterException("OpenCode changed a parsed client tool call", ErrorCategory.UPSTREAM_5XX)
                                    tool_parts[key] = item
                                    if len(tool_parts) > 128 or sum(len(v["function"]["arguments"].encode()) for v in tool_parts.values()) > 8 * 1024 * 1024:
                                        raise RouterException("OpenCode client tool response exceeds bounds", ErrorCategory.UPSTREAM_5XX)
                            pid = part.get("id") or props.get("partID")
                            delta = ""
                            if kind == "message.part.updated" and part.get("messageID") in assistant_ids and part.get("type") in ("text", "reasoning"):
                                types[pid] = part["type"]
                                text, previous = part.get("text", ""), seen.get(pid, "")
                                if not text.startswith(previous):
                                    raise RouterException("OpenCode stream changed already-delivered text", ErrorCategory.UPSTREAM_5XX)
                                delta, seen[pid] = text[len(previous):], text
                            elif kind == "message.part.delta" and props.get("messageID") in assistant_ids and props.get("field") == "text":
                                delta = props.get("delta", "")
                                seen[pid] = seen.get(pid, "") + delta
                            if delta and pid in types:
                                size += len(delta.encode())
                                if size > 8 * 1024 * 1024:
                                    raise RouterException("Lingling response exceeds 8 MiB", ErrorCategory.UPSTREAM_5XX)
                                yield chunk({"reasoning_content" if types[pid] == "reasoning" else "content": delta})
                            if kind == "session.idle" or kind == "session.status" and props.get("status", {}).get("type") == "idle":
                                if continuing:
                                    continue
                                invocations = [v for (mid, _), v in tool_parts.items() if final and mid == final["id"]]
                                if tools and final and final.get("finish") == "tool-calls" and not invocations and denials:
                                    if denials >= 3:
                                        raise RouterException("OpenCode repeatedly requested native tools instead of client tools", ErrorCategory.UPSTREAM_5XX)
                                    final = None
                                    continuing = True
                                    await call("POST", f"/session/{sid}/prompt_async", json={**prompt, "parts": [{"type": "text", "text":
                                        "The native tool/question was denied and cannot execute. Continue the original request using only the advertised client MCP tools, or give an ordinary text answer."}]})
                                    continue
                                if final is None or final.get("finish") not in (("stop", "length", "tool-calls") if tools else ("stop", "length")):
                                    raise RouterException("OpenCode stream ended without a completed response", ErrorCategory.UPSTREAM_5XX)
                                if final["finish"] == "tool-calls" and not invocations:
                                    raise RouterException("OpenCode completed a tool turn without client calls", ErrorCategory.UPSTREAM_5XX)
                                if invocations and final["finish"] != "tool-calls":
                                    raise RouterException("OpenCode ended a client tool turn with an inconsistent finish", ErrorCategory.UPSTREAM_5XX)
                                if invocations and request.parallel_tool_calls is False and len(invocations) != 1:
                                    raise RouterException("OpenCode ignored parallel_tool_calls=False", ErrorCategory.UPSTREAM_5XX)
                                if not invocations and (request.tool_choice == "required" or isinstance(request.tool_choice, dict)):
                                    raise RouterException("OpenCode did not satisfy required tool_choice", ErrorCategory.UPSTREAM_5XX)
                                if invocations:
                                    yield chunk({"tool_calls": [{"index": i, **item} for i, item in enumerate(invocations)]})
                                tokens = [m.get("tokens") or {} for m in completed.values()]
                                cached = sum(int((t.get("cache") or {}).get("read", 0)) for t in tokens)
                                reasoning = sum(int(t.get("reasoning", 0)) for t in tokens)
                                inp = sum(int(t.get("input", 0)) + int((t.get("cache") or {}).get("read", 0)) + int((t.get("cache") or {}).get("write", 0)) for t in tokens)
                                out = sum(int(t.get("output", 0)) for t in tokens) + reasoning
                                usage = {"prompt_tokens": inp, "completion_tokens": out, "total_tokens": inp + out,
                                         "prompt_tokens_details": {"cached_tokens": cached},
                                         "completion_tokens_details": {"reasoning_tokens": reasoning}}
                                yield chunk(finish="tool_calls" if invocations else "length" if final["finish"] == "length" else "stop", usage=usage)
                                yield "data: [DONE]\n\n"
                                return
                        raise RouterException("OpenCode event stream disconnected before completion", ErrorCategory.UPSTREAM_5XX)
                finally:
                    # Shield the whole cleanup, not just worker shutdown: a cancelled abort
                    # must still delete the session and disconnect this request's schemas.
                    async def cleanup():
                        try:
                            try:
                                await client.post(f"/session/{sid}/abort", timeout=5)
                            finally:
                                await client.delete(f"/session/{sid}", timeout=5)
                        except httpx.HTTPError:
                            pass
                        finally:
                            if schema is not None:
                                try:
                                    disconnected = await client.post("/mcp/client/disconnect", timeout=5)
                                    disconnected.raise_for_status()
                                except (httpx.HTTPError, asyncio.CancelledError):
                                    # Never reuse a client carrying another request's connected schemas.
                                    await _stop_process(runtime["process"])
                                    if self._workers.get(str(runtime["root"])) is runtime:
                                        self._workers.pop(str(runtime["root"]), None)
                                finally:
                                    schema.unlink(missing_ok=True)
                    task = asyncio.create_task(cleanup())
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        await task
                        raise
        except (TimeoutError, httpx.HTTPError) as exc:
            raise normalize_upstream_error(exception=exc) from exc
