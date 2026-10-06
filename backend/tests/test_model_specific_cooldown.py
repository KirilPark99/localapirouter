import pytest
from app.core.circuit_breaker import circuit_breaker, CredentialStatus
from app.core.errors import ErrorCategory

@pytest.mark.asyncio
async def test_rate_limit_isolates_to_specific_model():
    """
    Verify that when model A returns HTTP 429 Rate Limit (even without model name in the error message,
    such as Gemini's 'Resource has been exhausted' or Anthropic's 'Rate limit exceeded: 5 RPM'),
    only model A enters cooldown, while model B on the SAME credential remains healthy and available.
    """
    cred_id = 88881
    circuit_breaker.reset(cred_id)

    # Gemini-style error message: does NOT contain the model name!
    gemini_429 = "Resource has been exhausted (e.g. check quota)."

    circuit_breaker.record_failure(
        cred_id=cred_id,
        category=ErrorCategory.RATE_LIMIT,
        retry_after=60,
        error_message=gemini_429,
        model_id="gemini-2.5-flash",
    )

    # 1. gemini-2.5-flash MUST be in cooldown
    avail_flash, reason = circuit_breaker.is_available(cred_id, "gemini-2.5-flash")
    assert avail_flash is False
    assert "in cooldown" in reason
    assert "RATE_LIMITED" in reason

    # 2. gemini-2.5-pro on the SAME credential MUST remain available!
    avail_pro, reason_pro = circuit_breaker.is_available(cred_id, "gemini-2.5-pro")
    assert avail_pro is True
    assert reason_pro == "OK"

    # 3. Another model like gemini-2.0-flash on the SAME credential MUST remain available!
    avail_flash2, reason_flash2 = circuit_breaker.is_available(cred_id, "gemini-2.0-flash")
    assert avail_flash2 is True
    assert reason_flash2 == "OK"

    # 4. Status checks:
    # Model-specific status for flash: RATE_LIMITED
    status_flash = circuit_breaker.get_status(cred_id, "gemini-2.5-flash")
    assert status_flash["status"] == CredentialStatus.RATE_LIMITED
    assert status_flash["cooldown_remaining_seconds"] > 0

    # Model-specific status for pro: HEALTHY
    status_pro = circuit_breaker.get_status(cred_id, "gemini-2.5-pro")
    assert status_pro["status"] == CredentialStatus.HEALTHY
    assert status_pro["cooldown_remaining_seconds"] == 0

    # Credential-level status: DEGRADED (key is working, but some models are in cooldown)
    status_cred = circuit_breaker.get_status(cred_id)
    assert status_cred["status"] == CredentialStatus.DEGRADED
    assert "gemini-2.5-flash" in status_cred["model_cooldowns"]

    # 5. Late success preserves cooldown; only a success after expiry clears it.
    from datetime import datetime, timezone, timedelta
    circuit_breaker.record_success(cred_id, "gemini-2.5-flash")
    assert not circuit_breaker.is_available(cred_id, "gemini-2.5-flash")[0]
    circuit_breaker._model_cooldown_until[(cred_id, "gemini-2.5-flash")] = datetime.now(timezone.utc) - timedelta(seconds=1)
    circuit_breaker.record_success(cred_id, "gemini-2.5-flash")
    avail_flash_recovered, _ = circuit_breaker.is_available(cred_id, "gemini-2.5-flash")
    assert avail_flash_recovered is True
    assert circuit_breaker.get_status(cred_id)["status"] == CredentialStatus.HEALTHY


@pytest.mark.asyncio
async def test_canonical_slug_and_short_id_resolution():
    """
    Verify that cooldown applies regardless of whether canonical slug (provider/model)
    or short provider_model_id is used.
    """
    cred_id = 88882
    circuit_breaker.reset(cred_id)

    circuit_breaker.record_failure(
        cred_id=cred_id,
        category=ErrorCategory.RATE_LIMIT,
        retry_after=45,
        error_message="Too Many Requests",
        model_id="openai/gpt-4o",
    )

    # Both canonical and short ID should be recognized as in cooldown
    avail_canon, _ = circuit_breaker.is_available(cred_id, "openai/gpt-4o")
    assert avail_canon is False

    avail_short, _ = circuit_breaker.is_available(cred_id, "gpt-4o")
    assert avail_short is False

    # Other models on the same key remain healthy
    avail_mini, _ = circuit_breaker.is_available(cred_id, "openai/gpt-4o-mini")
    assert avail_mini is True

    avail_o3, _ = circuit_breaker.is_available(cred_id, "o3-mini")
    assert avail_o3 is True


@pytest.mark.asyncio
async def test_account_wide_quota_exhaustion_locks_credential():
    """
    Verify that genuine account-wide billing/quota exhaustion (e.g. 'insufficient_quota')
    locks the whole credential across all models as expected.
    """
    cred_id = 88883
    circuit_breaker.reset(cred_id)

    billing_error = "You exceeded your current quota, please check your plan and billing details. (insufficient_quota)"

    circuit_breaker.record_failure(
        cred_id=cred_id,
        category=ErrorCategory.RATE_LIMIT,
        retry_after=120,
        error_message=billing_error,
        model_id="gpt-4o",
    )

    # Since error is account-wide billing exhaustion, the entire credential is locked
    avail_4o, _ = circuit_breaker.is_available(cred_id, "gpt-4o")
    assert avail_4o is False

    avail_mini, _ = circuit_breaker.is_available(cred_id, "gpt-4o-mini")
    assert avail_mini is False

    avail_cred, _ = circuit_breaker.is_available(cred_id)
    assert avail_cred is False

    st = circuit_breaker.get_status(cred_id)
    assert st["status"] == CredentialStatus.RATE_LIMITED
