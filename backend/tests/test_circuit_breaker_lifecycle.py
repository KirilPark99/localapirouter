import pytest
import uuid
import time
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, ProviderCredential
from app.core.circuit_breaker import circuit_breaker
from app.core.errors import ErrorCategory
from app.services.credential_service import CredentialService
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_circuit_breaker_full_lifecycle():
    """
    Verifies:
    1) Key starts as HEALTHY and available;
    2) Successive failures transition key to COOLDOWN / RATE_LIMITED;
    3) Key in cooldown is marked not available;
    4) Manual reset via admin endpoint resets status back to HEALTHY.
    """
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name="CB Provider", slug=f"cb-{run_id}", adapter_type="openai",
            base_url="https://api.openai.com/v1", models_endpoint="/models",
            chat_endpoint="/chat/completions", enabled=True,
            auth_type="bearer", auth_header="Authorization",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        c = await CredentialService.create_credential(db, data=type("Obj", (), {
            "provider_id": p.id, "name": "CB Key", "api_key": f"sk-cb-{run_id}",
            "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
            "tpm_limit": None, "max_concurrency": None,
        })())
        cred_id = c.id

    # 1. Initially Available
    circuit_breaker.reset(cred_id)
    avail, reason = circuit_breaker.is_available(cred_id)
    assert avail is True
    st = circuit_breaker.get_status(cred_id)
    assert st["status"] == "HEALTHY"
    assert st["consecutive_failures"] == 0

    # 2. Record multiple failures to trigger circuit breaking
    for _ in range(5):
        circuit_breaker.record_failure(
            cred_id,
            category=ErrorCategory.RATE_LIMIT,
            retry_after=60,
            error_message="Too Many Requests",
        )

    st_failed = circuit_breaker.get_status(cred_id)
    assert st_failed["consecutive_failures"] >= 5
    assert st_failed["status"] in ("RATE_LIMITED", "COOLDOWN", "DEGRADED")
    # Not available while in active cooldown
    avail_failed, _ = circuit_breaker.is_available(cred_id)
    assert avail_failed is False

    # 3. Success resets state back to HEALTHY
    circuit_breaker.record_success(cred_id)
    st_recovered = circuit_breaker.get_status(cred_id)
    assert st_recovered["status"] == "HEALTHY"
    assert st_recovered["consecutive_failures"] == 0
    avail_rec, _ = circuit_breaker.is_available(cred_id)
    assert avail_rec is True

    # 4. Trigger failure again and test manual reset via Admin API
    for _ in range(5):
        circuit_breaker.record_failure(cred_id, category=ErrorCategory.UPSTREAM_5XX, retry_after=120)
    avail_5xx, _ = circuit_breaker.is_available(cred_id)
    assert avail_5xx is False

    token = AuthService.create_access_token("admin")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reset_res = await client.post(f"/api/admin/credentials/{cred_id}/reset-circuit-breaker", headers=headers)
        assert reset_res.status_code == 200
        assert "Circuit breaker reset to HEALTHY" in reset_res.json()["message"]

    # Verify circuit breaker is now healthy and available again
    avail_final, _ = circuit_breaker.is_available(cred_id)
    assert avail_final is True
    assert circuit_breaker.get_status(cred_id)["status"] == "HEALTHY"
