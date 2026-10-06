"""Regression: optional module profile fields may be JSON null."""
import json

import httpx
import pytest

from app.adapters.module_adapter import CustomModuleAdapter
from app.modules.loader import ModuleLoader
from modules.codex_cli.handler import CodexCliAdapter
from modules.grok_builder_cli.handler import GrokBuilderCliAdapter


@pytest.mark.asyncio
@pytest.mark.parametrize("module_id,adapter_class", [
    ("codex_cli", CodexCliAdapter),
    ("grok_builder_cli", GrokBuilderCliAdapter),
])
async def test_null_optional_fields_reach_validation_without_strip_error(
    monkeypatch, module_id, adapter_class,
):
    adapter = adapter_class()
    monkeypatch.setattr(ModuleLoader, "get_adapter", lambda name: adapter if name == module_id else None)
    bridge = CustomModuleAdapter()
    fields = {"auto_detect_local": False, "auth_json": None,
              "access_token": None, "refresh_token": None}
    if module_id == "codex_cli":
        fields["account_id"] = None
    else:
        fields["key"] = None
        fields["email"] = None
    _, ctx = bridge._resolve_context(json.dumps(fields), {"module_id": module_id})
    assert ctx.credentials == fields
    assert adapter._resolve_raw_tokens(ctx) == {}
    ok, message, count = await adapter.validate_credentials(ctx)
    assert not ok and count == 0
    assert ("No " in message or "Missing CLI credentials" in message) and "NoneType" not in message

    # Explicit credentials still work when their optional siblings are null.
    fields["access_token"] = "  dummy-token  "
    _, ctx = bridge._resolve_context(json.dumps(fields), {"module_id": module_id})
    assert adapter._resolve_raw_tokens(ctx)["access_token"] == "dummy-token"
    assert (await adapter._get_valid_access_token(ctx))[0] == "dummy-token"

    def upstream(request):
        assert request.headers["Authorization"] == "Bearer dummy-token"
        return httpx.Response(200, json={"data": [{"id": "test-model"}]})

    monkeypatch.setattr(adapter, "create_http_client", lambda *args, **kwargs:
                        httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
    ok, message, count = await bridge.validate_credentials(
        base_url="", api_key=json.dumps(fields), extra_headers={},
        configuration={"module_id": module_id},
    )
    assert ok and count > 0, message
