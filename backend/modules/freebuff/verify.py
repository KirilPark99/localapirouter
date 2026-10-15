"""Isolated checks: python -I backend/modules/freebuff/verify.py [--runtime] [pytest args]."""
import asyncio
import ipaddress
import os
from pathlib import Path
import socket
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True
backend = Path(__file__).resolve().parents[2]
scratch = Path(os.environ.get('TMPDIR') or Path.home() / '.hermes/cache/scratch').resolve()
scratch.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
runtime = '--runtime' in args
if runtime:
    args.remove('--runtime')
path = os.environ.get('PATH', '/usr/bin:/bin')

with tempfile.TemporaryDirectory(prefix='freebuff-offline-', dir=scratch) as folder:
    private = Path(folder)
    db_file = private / ('myairouter_test_' + uuid.uuid4().hex + '.db')
    os.environ.clear()
    os.environ.update(PATH=path, TMPDIR=str(private), HOME=str(private / 'home'),
        XDG_STATE_HOME=str(private / 'state'), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
        DATABASE_URL='sqlite+aiosqlite:///' + str(db_file),
        ROUTER_MASTER_KEY='T1BFTkxZLVNZTlRIRVRJQy1URVNULUtFWS0xMjM0NTY=',
        JWT_SECRET='synthetic-freebuff-jwt-key-not-production',
        ADMIN_PASSWORD='synthetic-password-freebuff', FINGERPRINT_SALT='synthetic-freebuff-test-salt')
    if runtime:
        os.environ['FREEBUFF_RUNTIME_CHECK'] = '1'
    Path(os.environ['HOME']).mkdir()
    os.chdir(backend)
    sys.path.insert(0, str(backend))
    from pydantic_settings import BaseSettings
    original = BaseSettings.__init__
    def isolated(self, *a, **kw):
        kw['_env_file'] = None
        original(self, *a, **kw)
    BaseSettings.__init__ = isolated

    active = True
    def guard(event, values):
        if not active:
            return
        if event == 'socket.connect' and values[0].family in (socket.AF_INET, socket.AF_INET6):
            if not runtime or not ipaddress.ip_address(values[1][0]).is_loopback:
                raise AssertionError('External sockets forbidden')
        if event == 'open' and isinstance(values[0], (str, bytes)):
            target = Path(os.fsdecode(values[0])).resolve()
            if target.name.startswith('.env') or (
                target.suffix in ('.db', '.sqlite', '.sqlite3') and not target.is_relative_to(private)):
                raise AssertionError('Production settings/DB forbidden')
            if 'credentials' in target.parts and not target.is_relative_to(private):
                raise AssertionError('Real account files forbidden')
    sys.addaudithook(guard)
    from app.core.database import engine, AsyncSessionLocal, Base
    import app.models.entities
    assert Path(engine.url.database).resolve() == db_file
    assert AsyncSessionLocal.kw['bind'] is engine
    async def initialize():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    asyncio.run(initialize())
    import pytest
    result = pytest.main([*(args or ['tests/test_freebuff.py', 'tests/test_freebuff_login_admin.py', '-q']),
        '--noconftest', '-p', 'no:cacheprovider', '-p', 'pytest_asyncio.plugin', '-o', 'addopts='])
    active = False  # shutil cleanup uses relative dir_fd opens; application checks are finished.
    asyncio.run(engine.dispose())
    raise SystemExit(result)
