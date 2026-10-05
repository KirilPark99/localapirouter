import pytest
from app.security.base import GuardrailContext
from app.security.credential_masker import (
    CredentialMaskerGuardrail,
    redact_credentials,
    walk_and_redact,
)


def test_redact_credentials_openai():
    text = "Use key sk-proj-1234567890abcdef1234567890 to call OpenAI"
    redacted, detections, mod = redact_credentials(text)
    assert mod is True
    assert "[REDACTED:openai]" in redacted
    assert "sk-proj-" not in redacted


def test_redact_credentials_anthropic():
    text = "My secret is sk-ant-api03-abcdef1234567890abcdef"
    redacted, detections, mod = redact_credentials(text)
    assert mod is True
    assert "[REDACTED:anthropic]" in redacted


def test_redact_credentials_aws():
    text = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    redacted, detections, mod = redact_credentials(text)
    assert mod is True
    assert "[REDACTED:aws]" in redacted


def test_redact_credentials_github():
    text = "Personal token: ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
    redacted, detections, mod = redact_credentials(text)
    assert mod is True
    assert "[REDACTED:github]" in redacted


def test_redact_credentials_db_uri():
    text = "Connecting to postgresql://admin:SuperSecretPass123@db.prod.internal:5432/mydb"
    redacted, detections, mod = redact_credentials(text)
    assert mod is True
    assert "[REDACTED:connection_string]" in redacted
    assert "SuperSecretPass123" not in redacted


def test_redact_credentials_private_key():
    text = (
        "Here is key:\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y3...\n"
        "-----END RSA PRIVATE KEY-----\n"
        "done."
    )
    redacted, detections, mod = redact_credentials(text)
    assert mod is True
    assert "[REDACTED:private_key]" in redacted


def test_redact_credentials_jwt():
    text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozG4B1"
    redacted, detections, mod = redact_credentials(text)
    assert mod is True
    assert "[REDACTED:jwt]" in redacted or "[REDACTED:auth_header]" in redacted


@pytest.mark.asyncio
async def test_guardrail_bidirectional():
    guard = CredentialMaskerGuardrail(enabled=True, mask_inbound=True, mask_outbound=True)

    # 1. Inbound (messages)
    payload = {"messages": [{"role": "user", "content": "My key is sk-proj-1234567890abcdef1234567890"}]}
    context = GuardrailContext()
    res_in = await guard.pre_call(payload, context)
    assert res_in.modified is True
    assert "[REDACTED:openai]" in res_in.modified_payload["messages"][0]["content"]
    assert res_in.modified_payload is not payload

    # 2. Outbound (response)
    outbound_text = "Here is your key: sk-ant-api03-abcdef1234567890abcdef"
    res_out = await guard.post_call(outbound_text, context)
    assert res_out.modified is True
    assert "[REDACTED:anthropic]" in res_out.modified_content
