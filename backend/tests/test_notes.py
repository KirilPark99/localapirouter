import pytest
import uuid
from app.core.database import AsyncSessionLocal
from app.services.provider_service import ProviderService
from app.schemas.entities import ProviderCreate, ProviderUpdate
from app.modules.loader import ModuleLoader
from app.models.entities import Provider
from sqlalchemy import select


@pytest.mark.asyncio
async def test_provider_notes_crud():
    unique_slug = f"test-notes-prov-{uuid.uuid4().hex[:8]}"
    initial_note = "Important: rate limit is 60 RPM. Internal staging server."

    async with AsyncSessionLocal() as db:
        # 1. Create provider with notes
        p_create = ProviderCreate(
            name="Notes Test Provider",
            slug=unique_slug,
            adapter_type="generic_openai",
            base_url="https://api.test.com/v1",
            notes=initial_note,
        )
        created = await ProviderService.create_provider(db, p_create)
        assert created.notes == initial_note

        # 2. Get provider
        fetched = await ProviderService.get_provider(db, created.id)
        assert fetched is not None
        assert fetched.notes == initial_note

        # 3. Update notes via update_provider_notes
        updated_note = "Updated: limit increased to 120 RPM. Use Proxy-02."
        res_note = await ProviderService.update_provider_notes(db, created.id, updated_note)
        assert res_note == updated_note

        fetched_again = await ProviderService.get_provider(db, created.id)
        assert fetched_again.notes == updated_note

        # 4. Update via standard update_provider
        via_update = "Changed via general update"
        p_up = await ProviderService.update_provider(db, created.id, ProviderUpdate(notes=via_update))
        assert p_up.notes == via_update

        # 5. Clear notes
        cleared = await ProviderService.update_provider_notes(db, created.id, "")
        assert cleared is None

        fetched_cleared = await ProviderService.get_provider(db, created.id)
        assert fetched_cleared.notes is None

        # Clean up
        await ProviderService.delete_provider(db, created.id)


@pytest.mark.asyncio
async def test_module_notes_crud():
    async with AsyncSessionLocal() as db:
        if not ModuleLoader._modules:
            ModuleLoader.scan_modules()
        await ModuleLoader.sync_with_db(db)

        # Pick first ready module
        ready_mods = [m for m in ModuleLoader._modules.values() if m.status == "ready"]
        assert len(ready_mods) > 0, "Expected at least one ready module"
        target_mod = ready_mods[0]
        mod_id = target_mod.manifest.id
        prov_slug = f"module_{mod_id}"

        # Check provider exists
        prov = (await db.execute(select(Provider).where(Provider.slug == prov_slug))).scalar_one_or_none()
        assert prov is not None, f"Expected provider record for module {mod_id}"

        # Update note
        test_note = "Custom module note: requires rotating UK proxies."
        prov.notes = test_note
        await db.commit()
        await db.refresh(prov)

        # Verify through query
        prov_check = (await db.execute(select(Provider).where(Provider.slug == prov_slug))).scalar_one_or_none()
        assert prov_check.notes == test_note

        # Clear note
        prov_check.notes = None
        await db.commit()


@pytest.mark.asyncio
async def test_credential_notes_crud():
    async with AsyncSessionLocal() as db:
        # Create a provider for testing credential
        p_slug = f"test-cred-notes-prov-{uuid.uuid4().hex[:8]}"
        p_create = ProviderCreate(
            name="Cred Notes Test Prov",
            slug=p_slug,
            adapter_type="generic_openai",
            base_url="https://api.test.com/v1",
        )
        prov = await ProviderService.create_provider(db, p_create)

        from app.services.credential_service import CredentialService
        from app.schemas.entities import CredentialCreate, CredentialUpdate

        # 1. Create credential with notes
        cred_note = "Account tier: Paid Pro. Exp: 2026-12."
        cred_create = CredentialCreate(
            provider_id=prov.id,
            name="Key With Notes",
            api_key=f"sk-test-{uuid.uuid4().hex}",
            notes=cred_note,
        )
        created_cred = await CredentialService.create_credential(db, cred_create)
        assert created_cred.notes == cred_note

        # 2. Get credential and check notes
        fetched_cred = await CredentialService.get_credential(db, created_cred.id)
        assert fetched_cred is not None
        assert fetched_cred.notes == cred_note

        # 3. Update notes via update_credential_notes
        updated_note = "Updated: billing card replaced, limit increased."
        res_note = await CredentialService.update_credential_notes(db, created_cred.id, updated_note)
        assert res_note == updated_note

        fetched_again = await CredentialService.get_credential(db, created_cred.id)
        assert fetched_again.notes == updated_note

        # 4. Update via general update_credential
        via_update = "Changed via general CredentialUpdate"
        up_cred = await CredentialService.update_credential(db, created_cred.id, CredentialUpdate(notes=via_update))
        assert up_cred.notes == via_update

        # 5. Clear notes
        cleared = await CredentialService.update_credential_notes(db, created_cred.id, "")
        assert cleared is None

        # Clean up
        await CredentialService.delete_credential(db, created_cred.id)
        await ProviderService.delete_provider(db, prov.id)


@pytest.mark.asyncio
async def test_router_api_key_notes_crud():
    async with AsyncSessionLocal() as db:
        from app.services.api_key_service import ApiKeyService
        from app.schemas.entities import RouterApiKeyCreate, RouterApiKeyUpdate

        # 1. Create key with notes
        initial_note = "Assigned to client app: Mobile iOS Client v2.3"
        key_create = RouterApiKeyCreate(
            name="Test Router Key",
            permissions=["direct", "routes"],
            notes=initial_note,
        )
        created = await ApiKeyService.create_key(db, key_create)
        assert created.notes == initial_note

        # 2. Get key
        fetched = await ApiKeyService.get_key(db, created.id)
        assert fetched is not None
        assert fetched.notes == initial_note

        # 3. Update notes via update_key_notes
        updated_note = "Client moved to enterprise plan. Monthly review."
        res = await ApiKeyService.update_key_notes(db, created.id, updated_note)
        assert res == updated_note

        fetched_again = await ApiKeyService.get_key(db, created.id)
        assert fetched_again.notes == updated_note

        # 4. Update via general update_key
        via_update = "General update test note"
        up_res = await ApiKeyService.update_key(db, created.id, RouterApiKeyUpdate(notes=via_update))
        assert up_res.notes == via_update

        # 5. Clear notes
        cleared = await ApiKeyService.update_key_notes(db, created.id, "")
        assert cleared is None

        # Clean up
        await ApiKeyService.delete_key(db, created.id)
