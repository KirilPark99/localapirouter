import os
import sys
import json
import logging
import inspect
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.base import BaseModuleAdapter, ModuleManifest, ModuleDefaultModel
from app.models.entities import Provider, DiscoveredModel

logger = logging.getLogger("app.modules.loader")

# Path to modules folder: backend/modules
MODULES_DIR = Path(__file__).resolve().parent.parent.parent / "modules"


class LoadedModule(BaseModel):
    manifest: ModuleManifest
    status: str = "ready"  # "ready" | "error"
    error: Optional[str] = None
    profiles_count: int = 0
    models_count: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ModuleLoader:
    _modules: Dict[str, LoadedModule] = {}
    _adapters: Dict[str, BaseModuleAdapter] = {}

    @classmethod
    def get_modules_dir(cls) -> Path:
        os.makedirs(MODULES_DIR, exist_ok=True)
        return MODULES_DIR

    @classmethod
    def get_module(cls, module_id: str) -> Optional[LoadedModule]:
        return cls._modules.get(module_id)

    @classmethod
    def get_adapter(cls, module_id: str) -> Optional[BaseModuleAdapter]:
        return cls._adapters.get(module_id)

    @classmethod
    def list_modules(cls) -> List[LoadedModule]:
        return list(cls._modules.values())

    @classmethod
    def scan_modules(cls) -> Dict[str, LoadedModule]:
        """
        Scan `backend/modules` directory for custom provider modules.
        Skips folders starting with '_' (e.g. `_template`) or '.'
        """
        modules_dir = cls.get_modules_dir()
        discovered: Dict[str, LoadedModule] = {}
        adapters: Dict[str, BaseModuleAdapter] = {}

        if not modules_dir.exists():
            cls._modules = {}
            cls._adapters = {}
            return {}

        for item in sorted(modules_dir.iterdir()):
            if not item.is_dir():
                continue
            name = item.name
            # Skip templates, hidden, and private directories
            if name.startswith("_") or name.startswith("."):
                continue

            manifest_path = item / "manifest.json"
            handler_path = item / "handler.py"

            if not manifest_path.exists():
                logger.warning(f"Module folder '{name}' is missing manifest.json; skipping")
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)

                manifest_data["folder_path"] = str(item)
                manifest = ModuleManifest(**manifest_data)
            except Exception as e:
                logger.error(f"Failed to parse manifest.json for module '{name}': {e}")
                err_manifest = ModuleManifest(
                    id=name,
                    name=name,
                    description=f"Manifest parsing error: {e}",
                    folder_path=str(item),
                )
                discovered[name] = LoadedModule(
                    manifest=err_manifest,
                    status="error",
                    error=f"Invalid manifest.json: {str(e)}",
                )
                continue

            if not handler_path.exists():
                discovered[manifest.id] = LoadedModule(
                    manifest=manifest,
                    status="error",
                    error="Missing handler.py in module directory",
                )
                continue

            # Dynamically import handler.py
            try:
                module_name = f"app_custom_module_{manifest.id}"
                if str(item) not in sys.path:
                    sys.path.insert(0, str(item))
                spec = importlib.util.spec_from_file_location(module_name, str(handler_path))
                if spec is None or spec.loader is None:
                    raise ImportError(f"Cannot create module spec for {handler_path}")

                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)

                # Find subclass of BaseModuleAdapter
                adapter_cls = None
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, BaseModuleAdapter)
                        and attr is not BaseModuleAdapter
                    ):
                        adapter_cls = attr
                        break

                if not adapter_cls:
                    raise TypeError(f"No subclass of BaseModuleAdapter found in {handler_path}")

                adapter_instance = adapter_cls()
                adapters[manifest.id] = adapter_instance
                discovered[manifest.id] = LoadedModule(
                    manifest=manifest,
                    status="ready",
                    error=None,
                )
                logger.info(f"Successfully loaded custom module: '{manifest.name}' ({manifest.id})")

            except Exception as e:
                logger.error(f"Failed to load handler for module '{manifest.id}': {e}", exc_info=True)
                discovered[manifest.id] = LoadedModule(
                    manifest=manifest,
                    status="error",
                    error=f"Handler execution error: {str(e)}",
                )

        cls._modules = discovered
        cls._adapters = adapters
        return cls._modules

    @classmethod
    async def sync_with_db(cls, db: AsyncSession) -> None:
        """
        Synchronize loaded modules with the providers and discovered_models tables in the database.
        """
        for module_id, loaded in cls._modules.items():
            if loaded.status != "ready":
                continue

            manifest = loaded.manifest
            provider_slug = f"module_{manifest.id}"

            # 1. Ensure Provider exists
            query = select(Provider).where(Provider.slug == provider_slug)
            result = await db.execute(query)
            provider = result.scalar_one_or_none()

            config = {
                "module_id": manifest.id,
                "manifest": manifest.model_dump(),
                "default_models": [m.id for m in manifest.default_models],
            }

            if not provider:
                provider = Provider(
                    name=manifest.name,
                    slug=provider_slug,
                    adapter_type="custom_module",
                    base_url=f"module://{manifest.id}",
                    models_endpoint="/models",
                    chat_endpoint="/chat/completions",
                    responses_endpoint="/responses",
                    auth_type="bearer",
                    auth_header="Authorization",
                    extra_headers={},
                    configuration=config,
                    enabled=True,
                )
                db.add(provider)
                await db.flush()
                logger.info(f"Created Provider record for custom module '{manifest.name}' (ID: {provider.id})")
            else:
                provider.name = manifest.name
                provider.configuration = config
                await db.flush()

            # 2. Count active profiles and models
            from app.models.entities import ProviderCredential
            from sqlalchemy import func
            cred_count = await db.scalar(
                select(func.count(ProviderCredential.id)).where(ProviderCredential.provider_id == provider.id)
            ) or 0
            loaded.profiles_count = cred_count

            # 3. Seed or update default models
            existing_models = (await db.execute(
                select(DiscoveredModel).where(DiscoveredModel.provider_id == provider.id)
            )).scalars().all()
            existing_map = {m.provider_model_id: m for m in existing_models}

            if manifest.default_models:
                manifest_ids = {def_model.id for def_model in manifest.default_models}
                for def_model in manifest.default_models:
                    canonical_slug = f"{manifest.id}/{def_model.id}"
                    if def_model.id in existing_map:
                        m_obj = existing_map[def_model.id]
                        m_obj.display_name = def_model.name
                        m_obj.capabilities = def_model.capabilities
                        m_obj.context_length = def_model.context_length
                        m_obj.max_output_tokens = def_model.max_output_tokens
                        m_obj.reasoning_effort = def_model.reasoning_effort
                    else:
                        m_obj = DiscoveredModel(
                            provider_id=provider.id,
                            credential_id=None,
                            provider_model_id=def_model.id,
                            display_name=def_model.name,
                            canonical_slug=canonical_slug,
                            capabilities=def_model.capabilities,
                            supported_endpoints=["/chat/completions"],
                            context_length=def_model.context_length,
                            max_output_tokens=def_model.max_output_tokens,
                            reasoning_effort=def_model.reasoning_effort,
                            enabled=True,
                            available=True,
                            is_visible=True,
                            model_type="openai",
                        )
                        db.add(m_obj)

                # Remove obsolete models that are no longer part of the module manifest
                for old_id, old_obj in existing_map.items():
                    if old_id not in manifest_ids:
                        await db.delete(old_obj)

                await db.flush()

            # Refresh count
            all_models = (await db.execute(
                select(DiscoveredModel).where(DiscoveredModel.provider_id == provider.id)
            )).scalars().all()
            loaded.models_count = len(all_models)
            logger.info(f"Synchronized models for module '{manifest.name}' (Total: {len(all_models)})")

        await db.commit()

        # Synchronize external file-based profiles from the profiles directory
        try:
            from app.modules.profile_loader import sync_profiles_from_disk
            profile_sync_res = await sync_profiles_from_disk(db)
            logger.info(f"File-based profiles sync completed: {profile_sync_res}")
        except Exception as e:
            logger.error(f"Failed to sync file-based profiles from disk: {e}", exc_info=True)

        # Refresh profiles count on all loaded modules
        from app.models.entities import ProviderCredential
        from sqlalchemy import func
        for module_id, loaded in cls._modules.items():
            if loaded.status != "ready":
                continue
            provider_slug = f"module_{loaded.manifest.id}"
            prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()
            if prov:
                cred_count = await db.scalar(
                    select(func.count(ProviderCredential.id)).where(ProviderCredential.provider_id == prov.id)
                ) or 0
                loaded.profiles_count = cred_count

    @classmethod
    async def reload_and_sync(cls, db: AsyncSession) -> Dict[str, Any]:
        """Rescan modules from disk and synchronize with the database."""
        cls.scan_modules()
        await cls.sync_with_db(db)
        return {
            "success": True,
            "total_modules": len(cls._modules),
            "ready_count": sum(1 for m in cls._modules.values() if m.status == "ready"),
            "modules": [m.model_dump() for m in cls._modules.values()],
        }
