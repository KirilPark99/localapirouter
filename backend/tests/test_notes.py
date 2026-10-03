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
