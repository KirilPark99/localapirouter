"""Isolated profile regression; runnable with pytest --noconftest or directly.

The child disables dotenv before app imports, uses a unique private SQLite DB,
blocks provider transports/browser launches and never scans real profiles.
"""
import os
from pathlib import Path
import subprocess
import sys


def test_offline_profile_loader_regressions():
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    result = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--offline-check"],
                            env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "profile regressions: PASS" in result.stdout


def offline_check():
    import asyncio
    import hashlib
    import json
    import socket
    import tempfile
    from contextlib import ExitStack
    from unittest.mock import patch
    from cryptography.fernet import Fernet
    from pydantic_settings import BaseSettings

    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    scratch = Path(os.environ.get("TMPDIR", str(Path.home() / ".hermes/cache/scratch")))
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="profile-regression-", dir=scratch) as directory, ExitStack() as guards:
        work = Path(directory)
        database = work / "private.sqlite3"
        os.environ.update(DATABASE_URL="sqlite+aiosqlite:///" + str(database),
            ROUTER_MASTER_KEY=Fernet.generate_key().decode(), JWT_SECRET="synthetic-profile-jwt-" + "x" * 32,
            ADMIN_PASSWORD="synthetic-profile-password", FINGERPRINT_SALT="synthetic-profile-salt",
            PROFILES_DIR=str(work / "unused-profiles"))
        original_init = BaseSettings.__init__
        def no_dotenv(self, **kwargs):
            original_init(self, **{**kwargs, "_env_file": None})
        def blocked(*args, **kwargs):
            raise AssertionError("Network, discovery and native browsers forbidden")
        guards.enter_context(patch.object(BaseSettings, "__init__", no_dotenv))
        for name in ("connect", "connect_ex"):
            guards.enter_context(patch.object(socket.socket, name, blocked))
        from curl_cffi.requests import AsyncSession as CurlSession
        from playwright.async_api import BrowserType
        guards.enter_context(patch.object(CurlSession, "request", blocked))
        for name in ("launch", "launch_persistent_context", "connect", "connect_over_cdp"):
            guards.enter_context(patch.object(BrowserType, name, blocked))
        from app.core.database import engine, Base, AsyncSessionLocal
        from app.core.crypto import encrypt_secret, decrypt_secret
        from app.models.entities import Provider, ProviderCredential, DiscoveredModel, CredentialModelPreference, Proxy
        from app.modules.base import ModuleManifest
        from app.modules.loader import ModuleLoader, LoadedModule
        from app.modules import profile_loader as loader
        from app.services.model_discovery_service import ModelDiscoveryService
        from sqlalchemy import select
        import yaml

        assert Path(engine.url.database).resolve() == database.resolve()
        assert AsyncSessionLocal.kw["bind"] is engine
        guards.enter_context(patch.object(ModuleLoader, "scan_modules", blocked))
        guards.enter_context(patch.object(ModuleLoader, "sync_with_db", blocked))
        guards.enter_context(patch.object(ModelDiscoveryService, "fetch_models_for_credential", blocked))
        guards.enter_context(patch.object(subprocess, "Popen", blocked))
        guards.enter_context(patch.object(asyncio, "create_subprocess_exec", blocked))
        guards.enter_context(patch.object(asyncio, "create_subprocess_shell", blocked))
        manifest = ModuleManifest(id="synthetic_web", name="Synthetic", fields=[
            {"key": "cookie", "label": "Cookie", "type": "password"},
            {"key": "retired_secret", "label": "Retired", "type": "password"}])
        ModuleLoader._modules = {manifest.id: LoadedModule(manifest=manifest)}
        ModuleLoader._adapters = {}
        mid = manifest.id
        fields = {"cookie": "synthetic-secret", "refresh_token": "synthetic-refresh",
                  "storage_state": {"cookies": [{"name": "x", "value": "synthetic"}]},
                  "flag": False, "count": 7, "items": ["a", 3], "extra_secret": "old-secret"}
        rules = [{"period": "hour", "requests": 4, "tokens": 500, "usd": 0.5},
                 {"scope": "model", "model": mid + "/second", "period": "day", "requests": 3}]
        source_root = work / "source"
        source = source_root / mid / "account.json"
        source.parent.mkdir(parents=True)
        payload = {"module": mid, "name": "Complete", "enabled": True, "priority": 3, "weight": 7,
            "group_name": "group", "rpm_limit": 5, "tpm_limit": 600, "max_concurrency": 2,
            "notes": "notes", "fields": fields, "quota_rules": rules,
            "model_preferences": [mid + "/second", mid + "/first"]}
        source.write_text(json.dumps(payload))

        async def get(name):
            async with AsyncSessionLocal() as db:
                return await db.scalar(select(ProviderCredential).where(ProviderCredential.name == name))

        async def sync(root=source_root):
            async with AsyncSessionLocal() as db:
                return await loader.sync_profiles_from_disk(db, root)

        async def preferences(cid):
            async with AsyncSessionLocal() as db:
                return (await db.scalars(select(DiscoveredModel.canonical_slug).join(CredentialModelPreference,
                    CredentialModelPreference.model_id == DiscoveredModel.id).where(CredentialModelPreference.credential_id == cid)
                    .order_by(CredentialModelPreference.priority_order))).all()

        async def main():
            # Every DDL/DML operation is tied to this unique fixture engine.
            assert Path(engine.url.database).resolve() == database.resolve() and AsyncSessionLocal.kw["bind"] is engine
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                prov = Provider(name="Synthetic", slug="module_" + mid, adapter_type="custom_module",
                    base_url="module://" + mid, configuration={"module_id": mid})
                db.add(prov)
                await db.flush()
                for name in ("first", "second"):
                    db.add(DiscoveredModel(provider_id=prov.id, canonical_slug=mid + "/" + name,
                        provider_model_id=name, display_name=name))
                proxy = Proxy(name="Synthetic proxy", scheme="http", host="synthetic.invalid", port=8080)
                db.add(proxy)
                await db.commit()
                payload["proxy_id"] = proxy.id
            source.write_text(json.dumps(payload))
            result = await sync()
            assert result["created"] == 1 and not result["errors"], result
            cred = await get("Complete")
            cid = cred.id
            assert json.loads(decrypt_secret(cred.encrypted_api_key)) == fields
            assert not (set(fields) & set(cred.metadata_json))
            assert cred.metadata_json["_file_hash"] == hashlib.sha256(source.read_bytes()).hexdigest()
            assert await preferences(cid) == payload["model_preferences"]
            for key in ("group_name", "rpm_limit", "tpm_limit", "max_concurrency", "proxy_id", "priority", "weight", "notes"):
                assert getattr(cred, key) == payload[key]
            rule_ids = [r["id"] for r in cred.quota_rules]
            assert len(set(rule_ids)) == 2
            await sync()
            assert [r["id"] for r in (await get("Complete")).quota_rules] == rule_ids

            # Full export, metadata durability, no plaintext merge and private atomic publication.
            async with AsyncSessionLocal() as db:
                current = await db.get(ProviderCredential, cid)
                current.metadata_json = {**current.metadata_json, **fields, "retired_secret": "synthetic-retired", "safe_info": {"a": 1}, "_internal": "keep"}
                await db.commit()
                out = await loader.export_profile_to_file(db, cid, mid, target_profiles_dir=work / "exports-json")
                yout = await loader.export_profile_to_file(db, cid, mid, "yaml", work / "exports-yaml")
            exported = json.loads(Path(out["file_path"]).read_text())
            assert yaml.safe_load(Path(yout["file_path"]).read_text()) == exported
            assert exported["fields"] == fields and "safe_info" not in exported["fields"]
            assert exported["model_preferences"] == payload["model_preferences"]
            assert Path(out["file_path"]).stat().st_mode & 0o777 == 0o600
            assert not list(Path(out["file_path"]).parent.glob(".profile-*"))
            cred = await get("Complete")
            assert cred.metadata_json["safe_info"] == {"a": 1} and cred.metadata_json["_internal"] == "keep"
            assert not ((set(fields) | {"retired_secret"}) & set(cred.metadata_json))
            assert cred.metadata_json["_file_path"] == yout["relative_path"]
            assert cred.metadata_json["_file_hash"] == hashlib.sha256(Path(yout["file_path"]).read_bytes()).hexdigest()

            # Portable import into another credential; destination IDs are generated locally.
            exported["name"] = "Fresh import"
            exported["enabled"] = False
            fresh_root = work / "fresh"
            fresh_file = fresh_root / mid / "fresh.json"
            fresh_file.parent.mkdir(parents=True)
            fresh_file.write_text(json.dumps(exported))
            result = await sync(fresh_root)
            assert result["created"] == 1 and not result["errors"], result
            fresh = await get("Fresh import")
            assert not fresh.enabled and (await get("Complete")).enabled  # Other roots are not pruned.
            assert json.loads(decrypt_secret(fresh.encrypted_api_key)) == fields
            for key in ("group_name", "rpm_limit", "tpm_limit", "max_concurrency", "proxy_id", "priority", "weight", "notes"):
                assert getattr(fresh, key) == payload[key]
            assert await preferences(fresh.id) == payload["model_preferences"]
            assert not set(rule_ids) & {r["id"] for r in fresh.quota_rules}

            # DB edit/token rotation survives unchanged source, including legacy missing hashes.
            async with AsyncSessionLocal() as db:
                fresh = await db.get(ProviderCredential, fresh.id)
                old_meta = fresh.metadata_json
                fresh.metadata_json = {**old_meta, **fields, "safe_info": "keep"}
                before = fresh.metadata_json
                loader.mark_profile_db_owned(fresh)
                assert fresh.metadata_json is not before and before.get("_file_db_owned") is False
                assert fresh.metadata_json["_file_db_owned"] and fresh.metadata_json["safe_info"] == "keep"
                assert not set(fields) & set(fresh.metadata_json)
                for key in ("_source", "_file_path", "_file_profile_key", "_file_hash"):
                    assert fresh.metadata_json[key] == old_meta[key]
                fresh.name = "DB renamed"
                fresh.group_name = "DB group"
                fresh.rpm_limit = 19
                fresh.notes = None
                fresh.proxy_id = None
                fresh.enabled = False
                fresh.encrypted_api_key = encrypt_secret(json.dumps({**fields, "refresh_token": "synthetic-rotated"}))
                await db.commit()
                fresh_id = fresh.id
            result = await sync(fresh_root)
            assert result["updated"] == 0 and not result["errors"], result
            changed = await get("DB renamed")
            assert not changed.enabled and changed.rpm_limit == 19 and changed.group_name == "DB group"
            assert changed.notes is None and changed.proxy_id is None
            assert json.loads(decrypt_secret(changed.encrypted_api_key))["refresh_token"] == "synthetic-rotated"
            async with AsyncSessionLocal() as db:
                changed = await db.get(ProviderCredential, fresh_id)
                changed.metadata_json = {k: v for k, v in changed.metadata_json.items() if k != "_file_hash"}
                await db.commit()
            await sync(fresh_root)
            changed = await get("DB renamed")
            assert changed.rpm_limit == 19 and changed.metadata_json["_file_hash"] == hashlib.sha256(fresh_file.read_bytes()).hexdigest()
            assert json.loads(decrypt_secret(changed.encrypted_api_key))["refresh_token"] == "synthetic-rotated"

            # Changed bytes mean intentional import and clear ownership; nullable settings clear.
            exported.update(name="Intentional import", enabled=True, proxy_id=None, notes=None, group_name=None,
                            rpm_limit=None, tpm_limit=None, max_concurrency=None, quota_rules=[], model_preferences=[])
            exported["fields"] = {"cookie": "synthetic-external"}
            fresh_file.write_text(json.dumps(exported))
            result = await sync(fresh_root)
            assert result["updated"] == 1 and not result["errors"], result
            changed = await get("Intentional import")
            # A name change changes the file key; matching the managed source path must keep identity.
            assert changed.id == fresh_id
            assert changed.enabled and not changed.metadata_json["_file_db_owned"]
            assert changed.metadata_json["safe_info"] == "keep" and not set(fields) & set(changed.metadata_json)
            assert changed.quota_rules == [] and await preferences(changed.id) == []
            for key in ("proxy_id", "notes", "group_name", "rpm_limit", "tpm_limit", "max_concurrency"):
                assert getattr(changed, key) is None

            # Bad JSON/schema, empty/scalar files and partial lists are errors, never deletions.
            valid = fresh_file.read_bytes()
            malformed = [b'{broken', b'', b'null', b'3', b'[{},3]', json.dumps({**exported, "quota_rules": [{"scope": "profile", "model": "route/test", "requests": 1}]}).encode(),
                         json.dumps({**exported, "quota_rules": [{"requests": 0}]}).encode(),
                         json.dumps({**exported, "rpm_limit": 0}).encode()]
            for bad in malformed:
                fresh_file.write_bytes(bad)
                scan_errors = []
                assert loader.scan_disk_profiles(fresh_root, scan_errors) == [] and scan_errors
                result = await sync(fresh_root)
                assert result["errors"] and result["orphaned_disabled"] == 0, result
                assert (await get("Intentional import")).enabled
            fresh_file.write_bytes(valid)
            # Missing model fails before any profile mutation and reports an error.
            invalid = json.loads(valid)
            invalid["model_preferences"] = [mid + "/missing"]
            invalid["fields"] = {"cookie": "should-not-save"}
            fresh_file.write_text(json.dumps(invalid))
            result = await sync(fresh_root)
            assert result["errors"] and result["updated"] == 0
            assert json.loads(decrypt_secret((await get("Intentional import")).encrypted_api_key)) == exported["fields"]
            fresh_file.write_bytes(valid)
            await sync(fresh_root)
            fresh_file.unlink()
            assert (await sync(fresh_root))["orphaned_disabled"] == 1
            assert not (await get("Intentional import")).enabled

            # Colliding normalized names and changed source exports never clobber files.
            collision_root = work / "collision"
            untouched = collision_root / mid / "same_a.json"
            untouched.parent.mkdir(parents=True)
            untouched.write_text("unrelated")
            async with AsyncSessionLocal() as db:
                for name in ("Same/A", "Same A"):
                    db.add(ProviderCredential(provider_id=prov.id, name=name, encrypted_api_key=encrypt_secret(json.dumps(fields)), key_fingerprint=name, masked_key="masked"))
                await db.commit()
                paths = []
                for name in ("Same/A", "Same A"):
                    row = await db.scalar(select(ProviderCredential).where(ProviderCredential.name == name))
                    output = await loader.export_profile_to_file(db, row.id, mid, target_profiles_dir=collision_root)
                    paths.append(output["file_path"])
                assert len(set(paths)) == 2 and untouched.read_text() == "unrelated"
                # External modification of the linked export must be protected as well.
                protected = Path(paths[-1])
                protected.write_text("external edit")
                before = set(collision_root.rglob("*.json"))
                try:
                    await loader.export_profile_to_file(db, row.id, mid, target_profiles_dir=collision_root)
                except ValueError as exc:
                    assert "changed on disk" in str(exc)
                else:
                    raise AssertionError("Changed source must require explicit synchronization")
                assert protected.read_text() == "external edit" and set(collision_root.rglob("*.json")) == before
                # A creator racing the atomic publication must not be overwritten.
                real_link = loader.os.link
                raced = []
                def race_link(src, dst):
                    if not raced:
                        Path(dst).write_text("racing creator")
                        raced.append(Path(dst))
                    return real_link(src, dst)
                with patch.object(loader.os, "link", race_link):
                    output = await loader.export_profile_to_file(db, row.id, mid, target_profiles_dir=work / "race")
                assert raced[0].read_text() == "racing creator" and output["file_path"] != str(raced[0])
                assert Path(output["file_path"]).stat().st_mode & 0o777 == 0o600

            # Legacy top-level fields and multiple profiles in one file remain supported.
            list_root = work / "list"
            list_file = list_root / mid / "accounts.yaml"
            list_file.parent.mkdir(parents=True)
            list_file.write_text(yaml.safe_dump([{"name": "List one", "cookie": "synthetic-one"},
                                                {"name": "List two", "fields": {"cookie": "synthetic-two"}}]))
            result = await sync(list_root)
            assert result["created"] == 2 and not result["errors"], result
            one, two = await get("List one"), await get("List two")
            assert one.id != two.id
            assert json.loads(decrypt_secret(one.encrypted_api_key)) == {"cookie": "synthetic-one"}
            assert json.loads(decrypt_secret(two.encrypted_api_key)) == {"cookie": "synthetic-two"}
            assert (await sync(list_root))["updated"] == 2
            async with AsyncSessionLocal() as db:
                sibling = await db.get(ProviderCredential, two.id)
                loader.mark_profile_db_owned(sibling)
                sibling.encrypted_api_key=encrypt_secret(json.dumps({"cookie":"synthetic-rotated-sibling"}))
                await db.commit()
                output = await loader.export_profile_to_file(db,one.id,mid,"yaml",list_root)
                assert output["file_path"] == str(list_file) and len(yaml.safe_load(list_file.read_text())) == 2
            assert not (await sync(list_root))["errors"]
            assert json.loads(decrypt_secret((await get("List two")).encrypted_api_key))["cookie"] == "synthetic-rotated-sibling"
            (list_file.parent / "duplicate.json").write_text(json.dumps({"name": "List one", "fields": {}}))
            result = await sync(list_root)
            assert result["errors"] and result["orphaned_disabled"] == 0
            assert (await get("List one")).enabled
            (list_file.parent / "duplicate.json").unlink()
            list_file.write_text(yaml.safe_dump([{"name": "List one", "cookie": "synthetic-one"}]))
            assert (await sync(list_root))["orphaned_disabled"] == 1
            assert not (await get("List two")).enabled

            # Re-export updates its own unchanged source, not a duplicate auto-import file.
            repeat_root = work / "repeat"
            async with AsyncSessionLocal() as db:
                first = await loader.export_profile_to_file(db, cid, mid, target_profiles_dir=repeat_root)
                row = await db.get(ProviderCredential, cid)
                row.notes = "re-exported"
                loader.mark_profile_db_owned(row)
                await db.commit()
                second = await loader.export_profile_to_file(db, cid, mid, target_profiles_dir=repeat_root)
            assert first["file_path"] == second["file_path"]
            assert len(list(repeat_root.rglob("*.json"))) == 1
            assert json.loads(Path(second["file_path"]).read_text())["notes"] == "re-exported"
            assert not (await sync(repeat_root))["errors"]

            # Legacy files do not silently erase settings introduced after their format.
            legacy_root = work / "legacy"
            legacy = legacy_root / mid / "legacy.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(json.dumps({"name":"Legacy", "fields":{"cookie":"legacy"}}))
            assert not (await sync(legacy_root))["errors"]
            row = await get("Legacy")
            async with AsyncSessionLocal() as db:
                row = await db.get(ProviderCredential, row.id)
                row.rpm_limit=31;row.quota_rules=(await get("Complete")).quota_rules
                row.group_name="preserved";row.notes="preserved"
                db.add(CredentialModelPreference(credential_id=row.id,model_id=(await db.scalar(select(DiscoveredModel))).id,priority_order=0))
                await db.commit()
            assert not (await sync(legacy_root))["errors"]
            row = await get("Legacy")
            assert row.rpm_limit == 31 and row.group_name == "preserved" and row.notes == "preserved"
            assert row.quota_rules and len(await preferences(row.id)) == 1

            # UI metadata is scrubbed too, without converting it into a file profile.
            ui = ProviderCredential(name="UI", encrypted_api_key=encrypt_secret(json.dumps(fields)),
                metadata_json={**fields, "safe_info": "keep", "_internal": "keep"})
            loader.mark_profile_db_owned(ui)
            assert ui.metadata_json == {"safe_info": "keep", "_internal": "keep"}

            # Fail closed: corrupt encrypted data never exports legacy metadata or creates files.
            async with AsyncSessionLocal() as db:
                row = await db.get(ProviderCredential, cid)
                row.encrypted_api_key = "corrupt-synthetic"
                row.metadata_json = {"cookie": "plaintext-must-not-export"}
                await db.commit()
                for module in (mid, "different_module", "../escape"):
                    try:
                        await loader.export_profile_to_file(db, cid, module, target_profiles_dir=work / "corrupt")
                    except Exception:
                        pass
                    else:
                        raise AssertionError("Export should fail closed")
                assert not (work / "corrupt").exists()
            await engine.dispose()
            print("profile regressions: PASS (roundtrip, quotas, ownership/hash, metadata, malformed/deletion, atomic collisions, decrypt)")
        asyncio.run(main())


if __name__ == "__main__":
    offline_check()
