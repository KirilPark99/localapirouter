"""Finite cache lifetime and byte accounting using synthetic SQLite only."""
import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from app.cache import response_cache as module
from app.cache.response_cache import ResponseCacheService as Cache
from app.core.config import Settings, settings
from app.models.entities import ResponseCacheEntry
from test_response_cache_hardening import isolated_cache, RESPONSE


def test_finite_ttl_and_byte_accounting(tmp_path, monkeypatch):
    async def check():
        async with isolated_cache(tmp_path) as sessions, sessions() as db:
            for invalid in (0, -1, True, float('inf'), float('nan'), '60'):
                with pytest.raises(ValueError):
                    await Cache.set_response(db, 'v2:invalid', 'synthetic', RESPONSE, ttl_seconds=invalid)
            start = module._now()
            await Cache.set_response(db, 'v2:a', 'synthetic', RESPONSE)
            stored = await db.scalar(select(ResponseCacheEntry))
            assert start < stored.expires_at <= module._now() + timedelta(seconds=settings.RESPONSE_CACHE_TTL_SECONDS)
            size = Cache._memory_bytes
            assert size > len(str(RESPONSE).encode())
            monkeypatch.setattr(Cache, '_max_memory_bytes', size * 2 - 1)
            await Cache.set_response(db, 'v2:b', 'synthetic', RESPONSE)
            assert list(Cache._memory_cache) == ['v2:b']
            assert Cache._memory_bytes == size
            await Cache.set_response(db, 'v2:b', 'synthetic', RESPONSE)
            assert Cache._memory_bytes == size
            monkeypatch.setattr(module, '_now', lambda: stored.expires_at + timedelta(seconds=1))
            assert await Cache.get_response(db, 'v2:b') is None
            assert Cache._memory_bytes == 0
            await Cache.clear_cache(db)
            assert Cache._memory_bytes == 0
    asyncio.run(check())


def test_oversized_response_stays_out_of_ram(tmp_path, monkeypatch):
    async def check():
        async with isolated_cache(tmp_path) as sessions, sessions() as db:
            monkeypatch.setattr(Cache, '_max_memory_bytes', 512)
            await Cache.set_response(db, 'v2:large', 'synthetic', {'text': '界' * 10000})
            assert not Cache._memory_cache and Cache._memory_bytes == 0
            assert await Cache.get_response(db, 'v2:large') == {'text': '界' * 10000}
            assert not Cache._memory_cache and Cache._memory_bytes == 0
    asyncio.run(check())


@pytest.mark.parametrize('field,value', [('RESPONSE_CACHE_TTL_SECONDS', 0), ('RESPONSE_CACHE_TTL_SECONDS', float('inf')), ('RESPONSE_CACHE_MAX_BYTES', 0), ('RESPONSE_CACHE_MAX_BYTES', -1)])
def test_cache_settings_reject_invalid_limits(field, value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{field: value})
