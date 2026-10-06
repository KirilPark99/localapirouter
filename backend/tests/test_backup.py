import pytest
import json
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, ProviderCredential
from app.services.backup_service import BackupService, encrypt_payload, decrypt_payload
from app.core.crypto import encrypt_secret, decrypt_secret, compute_fingerprint, mask_secret
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_backup_export_and_import():
    async with AsyncSessionLocal() as db:
        # 1. Setup a test provider and credential
        p = Provider(
            name="Export Test OpenAI",
            slug="test-export-openai",
            adapter_type="openai",
            base_url="https://api.openai.com/v1",
            models_endpoint="/models",
            chat_endpoint="/chat/completions",
            enabled=True,
            auth_type="bearer",
            auth_header="Authorization",
            extra_headers={"X-Test": "1"},
            configuration={"folders": ["Prod", "Dev"]},
        )
        db.add(p)
        await db.flush()

        raw_key = "sk-test-secret-key-123456"
        fp = compute_fingerprint(raw_key)
        c = ProviderCredential(
            provider_id=p.id,
            name="Key Alpha",
            group_name="Prod",
            encrypted_api_key=encrypt_secret(raw_key),
            key_fingerprint=fp,
            masked_key=mask_secret(raw_key),
            enabled=True,
            status="HEALTHY",
            priority=1,
            weight=2,
            rpm_limit=100,
        )
        db.add(c)
        await db.commit()

        # 2. Exports are always encrypted because they contain decrypted keys.
        passphrase = "super-secure-passphrase-999"
        export_result = await BackupService.export_data(
            db, provider_ids=[p.id], include_proxies=False, passphrase=passphrase
        )
        assert export_result["encrypted"] is True
        data = decrypt_payload(export_result, passphrase=passphrase)
        assert len(data["providers"]) == 1
        assert data["providers"][0]["slug"] == "test-export-openai"
        assert len(data["credentials"]) == 1
        assert data["credentials"][0]["api_key"] == raw_key
        assert data["credentials"][0]["group_name"] == "Prod"

        # 3. Test export encrypted with passphrase
        enc_export = await BackupService.export_data(
            db, provider_ids=[p.id], include_proxies=False, passphrase=passphrase
        )
        assert enc_export["encrypted"] is True
        assert "ciphertext" in enc_export
        assert "salt" in enc_export

        # Decrypt with correct passphrase
        decrypted = decrypt_payload(enc_export, passphrase=passphrase)
        assert decrypted["providers"][0]["slug"] == "test-export-openai"

        # Decrypt with wrong passphrase -> raises ValueError
        with pytest.raises(ValueError):
            decrypt_payload(enc_export, passphrase="wrong-passphrase")

        # 4. Test preview_import
        preview = await BackupService.preview_import(db, export_result, passphrase=passphrase)
        assert preview["valid"] is True
        assert preview["total_providers"] == 1
        assert preview["existing_providers"] == 1
        assert preview["total_credentials"] == 1
        assert preview["existing_credentials"] == 1

        # 5. Test importing with a new provider and new credential
        import_payload = {
            "version": 1, "type": "myairouter_backup",
            "providers": [
                {
                    "name": "Export Test Anthropic",
                    "slug": "test-export-anthropic",
                    "adapter_type": "anthropic",
                    "base_url": "https://api.anthropic.com/v1",
                    "models_endpoint": "/models",
                    "chat_endpoint": "/messages",
                    "enabled": True,
                    "auth_type": "x-api-key",
                    "auth_header": "x-api-key",
                    "extra_headers": {},
                    "configuration": {"folders": ["ClaudeGroup"]},
                }
            ],
            "credentials": [
                {
                    "name": "Claude Key 1",
                    "provider_slug": "test-export-anthropic",
                    "api_key": "sk-ant-test-987654321",
                    "group_name": "ClaudeGroup",
                    "enabled": True,
                    "priority": 1,
                    "weight": 1,
                    "rpm_limit": 50,
                }
            ],
            "proxies": [],
        }

        import_res = await BackupService.import_data(
            db=db,
            raw_payload=encrypt_payload(import_payload, passphrase),
            passphrase=passphrase,
            update_existing_providers=True,
            skip_duplicate_credentials=True,
            auto_discover_models=False,
        )
        assert import_res["success"] is True
        assert import_res["imported_providers"] == 1
        assert import_res["imported_credentials"] == 1

        # Verify new provider and key in DB
        new_p_res = await db.execute(select(Provider).where(Provider.slug == "test-export-anthropic"))
        new_p = new_p_res.scalar_one()
        assert new_p.name == "Export Test Anthropic"

        new_c_res = await db.execute(select(ProviderCredential).where(ProviderCredential.provider_id == new_p.id))
        new_c = new_c_res.scalar_one()
        assert new_c.name == "Claude Key 1"
        assert new_c.group_name == "ClaudeGroup"
        # Decrypt with current server master key
        assert decrypt_secret(new_c.encrypted_api_key) == "sk-ant-test-987654321"


@pytest.mark.asyncio
async def test_backup_api_endpoints():
    token = AuthService.create_access_token("admin")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Export
        resp = await ac.post(
            "/api/admin/backup/export",
            json={"include_proxies": False, "passphrase": "api-backup-passphrase"},
            headers=headers,
        )
        assert resp.status_code == 200
        export_json = resp.json()
        assert "encrypted" in export_json

        # 2. Preview
        preview_resp = await ac.post(
            "/api/admin/backup/preview",
            json={"raw_payload": export_json, "passphrase": "api-backup-passphrase"},
            headers=headers,
        )
        assert preview_resp.status_code == 200
        preview_json = preview_resp.json()
        assert preview_json["valid"] is True

        # 3. Import
        import_resp = await ac.post(
            "/api/admin/backup/import",
            json={
                "raw_payload": export_json,
                "passphrase": "api-backup-passphrase",
                "update_existing_providers": True,
                "skip_duplicate_credentials": True,
                "auto_discover_models": False,
            },
            headers=headers,
        )
        assert import_resp.status_code == 200
        import_json = import_resp.json()
        assert import_json["success"] is True
