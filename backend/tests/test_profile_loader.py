import json
import pytest
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profile_loader import scan_disk_profiles, sync_profiles_from_disk, export_profile_to_file
from app.modules.loader import ModuleLoader
from app.models.entities import Provider, ProviderCredential
from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_scan_and_sync_disk_profiles(tmp_path: Path):
    # Setup test profiles directory structure
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    # 1. Notion profile in subfolder
    notion_dir = profiles_dir / "notion_web"
    notion_dir.mkdir()
    notion_file = notion_dir / "account1.json"
    notion_file.write_text(json.dumps({
        "name": "Test Notion Profile",
        "enabled": True,
        "priority": 2,
        "weight": 5,
        "fields": {
            "token_v2": "test_token_v2_secret"
        }
    }), encoding="utf-8")

    # 2. YAML profile in root
    yaml_file = profiles_dir / "duckduckgo_web.yaml"
    yaml_file.write_text("""
name: "Test DDG Profile"
enabled: true
priority: 1
fields: {}
""", encoding="utf-8")

    # 3. Example file should be ignored
    example_file = profiles_dir / "ignore_me.example.json"
    example_file.write_text(json.dumps({"name": "Ignored"}), encoding="utf-8")

    # Test scan
    scanned = scan_disk_profiles(profiles_dir)
    assert len(scanned) == 2
    scanned_names = {p.name for p in scanned}
    assert "Test Notion Profile" in scanned_names
    assert "Test DDG Profile" in scanned_names

    # Test sync to DB
    async with AsyncSessionLocal() as db:
        # Ensure modules are scanned and DB providers exist
        ModuleLoader.scan_modules()
        await ModuleLoader.sync_with_db(db)

        sync_result = await sync_profiles_from_disk(db, profiles_dir=profiles_dir)
        assert sync_result["total_scanned"] == 2
        assert sync_result["created"] >= 1 or sync_result["updated"] >= 1

        # Check DB records
        prov_notion = (await db.execute(
            select(Provider).where(Provider.slug == "module_notion_web")
        )).scalar_one_or_none()
        assert prov_notion is not None

        cred = (await db.execute(
            select(ProviderCredential).where(
                ProviderCredential.provider_id == prov_notion.id,
                ProviderCredential.name == "Test Notion Profile"
            )
        )).scalar_one_or_none()
        assert cred is not None
        assert cred.priority == 2
        assert cred.weight == 5
        assert cred.metadata_json.get("_source") == "file"

        # Test export
        export_res = await export_profile_to_file(db, cred.id, "notion_web", format_ext="json", target_profiles_dir=profiles_dir)
        assert export_res["success"] is True
        exported_path = Path(export_res["file_path"])
        assert exported_path.exists()
        exported_data = json.loads(exported_path.read_text(encoding="utf-8"))
        assert exported_data["name"] == "Test Notion Profile"
        assert exported_data["fields"]["token_v2"] == "test_token_v2_secret"
