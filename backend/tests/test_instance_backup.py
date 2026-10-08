"""Full-instance recovery checks. No production DB, .env, lifecycle or model calls."""
import base64
from contextlib import closing
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.entities import (Base, AdminUser, Provider, ProviderCredential, RoutingProfile,
                                FusionProfile, JudgeProfile, RouterApiKey, PeriodQuotaCounter,
                                SecurityConfig, AppSetting)

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/instance_backup.py'
spec = importlib.util.spec_from_file_location('instance_backup', SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
PASSWORD = 'synthetic-backup-password'


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    database = tmp_path / 'synthetic.sqlite3'
    values = settings.model_dump()
    values.update(DATABASE_URL='sqlite+aiosqlite:///' + str(database),
                  ROUTER_MASTER_KEY=Fernet.generate_key().decode(), JWT_SECRET='synthetic-jwt-' + 'x' * 32,
                  ADMIN_PASSWORD='synthetic-admin-password', FINGERPRINT_SALT='synthetic-fingerprint-salt')
    # Only synthetic dotenv input, converted to exported environment exactly as a launcher can do.
    envfile = tmp_path / '.env'
    envfile.write_text('\n'.join(key + '=' + json.dumps(str(values[key])) for key in
                                ('DATABASE_URL', 'ROUTER_MASTER_KEY', 'JWT_SECRET', 'ADMIN_PASSWORD', 'FINGERPRINT_SALT')))
    from dotenv import dotenv_values
    for key, value in dotenv_values(envfile).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('ADMIN_USERNAME', 'synthetic-owner')
    engine = create_engine('sqlite:///' + str(database))
    assert Path(engine.url.database).resolve() == database.resolve()
    Base.metadata.create_all(engine)
    encrypted = Fernet(values['ROUTER_MASTER_KEY'].encode()).encrypt(b'synthetic-provider-secret').decode()
    with Session(engine) as db:
        db.add(AdminUser(username='synthetic-owner', password_hash='synthetic-password-hash'))
        provider = Provider(name='Synthetic', slug='synthetic', adapter_type='generic_openai', base_url='https://synthetic.invalid')
        db.add(provider)
        db.flush()
        db.add(ProviderCredential(provider_id=provider.id, name='synthetic-key', encrypted_api_key=encrypted,
                                  key_fingerprint='synthetic-fingerprint', masked_key='synthetic-masked'))
        db.add_all([RoutingProfile(name='route', slug='route'), FusionProfile(name='fusion', slug='fusion'),
                    JudgeProfile(name='judge', slug='judge'), SecurityConfig(injection_mode='block'),
                    AppSetting(key='synthetic-policy', value_json={'enabled': True})])
        key = RouterApiKey(name='synthetic-router', key_prefix='test', key_hash='synthetic-key-hash', masked_key='masked',
                           permissions=['routes'], allowed_models=['synthetic/model'], total_requests=37,
                           quota_rules=[{'period': 'day', 'requests': 50}])
        db.add(key)
        db.flush()
        db.add(PeriodQuotaCounter(key_id=key.id, rule_identity='test-rule', window_start='synthetic-window', requests=7, tokens=111, usd=0.03))
        db.commit()
    engine.dispose()
    # Keep WAL open: the row below is not necessarily in the main SQLite file.
    live = sqlite3.connect(database)
    live.execute('PRAGMA journal_mode=WAL')
    live.execute('PRAGMA wal_autocheckpoint=0')
    live.execute('CREATE TABLE synthetic_wal (value TEXT)')
    live.execute("INSERT INTO synthetic_wal VALUES ('committed-wal-value')")
    live.commit()
    archive = tmp_path / 'full.encrypted.json'
    tool.backup(archive, PASSWORD)
    yield archive, database, values
    live.close()


def table_data(path):
    with closing(sqlite3.connect(path)) as db:
        names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {name: db.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall() for name in names}


def test_full_wal_roundtrip_settings_and_overwrite(synthetic, tmp_path):
    archive, source, values = synthetic
    target = tmp_path / 'recovered'
    tool.restore(archive, target, PASSWORD)
    assert table_data(source) == table_data(target / tool.DB_NAME)
    restored = json.loads((target / tool.SETTINGS_NAME).read_text())
    for key in ('ROUTER_MASTER_KEY', 'JWT_SECRET', 'ADMIN_PASSWORD', 'FINGERPRINT_SALT'):
        assert restored[key] == values[key]
    assert restored['ADMIN_USERNAME'] == 'synthetic-owner'
    with closing(sqlite3.connect(target / tool.DB_NAME)) as db:
        token = db.execute('SELECT encrypted_api_key FROM provider_credentials').fetchone()[0]
    assert Fernet(restored['ROUTER_MASTER_KEY'].encode()).decrypt(token.encode()) == b'synthetic-provider-secret'
    assert target.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in target.iterdir())
    assert archive.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match='overwrite'):
        tool.restore(archive, target, PASSWORD)
    tool.restore(archive, target, PASSWORD, overwrite=True)
    preserved = list(tmp_path.glob('recovered.before-*'))
    assert len(preserved) == 1
    assert table_data(preserved[0] / tool.DB_NAME) == table_data(source)


def test_wrong_password_tamper_traversal_and_no_clobber(synthetic, tmp_path):
    archive, _, _ = synthetic
    target = tmp_path / 'refused'
    with pytest.raises(ValueError):
        tool.restore(archive, target, 'synthetic-wrong-password')
    envelope = json.loads(archive.read_text())
    envelope['ciphertext'] = envelope['ciphertext'][:-10] + 'AAAAAAAAAA'
    tampered = tmp_path / 'tampered.json'
    tampered.write_text(json.dumps(envelope))
    with pytest.raises(ValueError):
        tool.restore(tampered, target, PASSWORD)
    with pytest.raises(ValueError, match='traversal'):
        tool.restore(archive, tmp_path / 'x/../refused', PASSWORD)
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='Symlink'):
        tool.restore(archive, link / 'refused', PASSWORD)
    encrypt, decrypt = tool.encrypt_payload, tool.decrypt_payload
    payload = decrypt(json.loads(archive.read_text()), PASSWORD)
    payload['../../.env'] = 'synthetic-malicious'
    tampered.write_text(json.dumps(encrypt(payload, PASSWORD)))
    with pytest.raises(ValueError, match='Unsupported'):
        tool.restore(tampered, target, PASSWORD)
    assert not target.exists()
    with pytest.raises(FileExistsError):
        tool.backup(archive, PASSWORD)


def test_restore_rejects_open_database_and_parallel_lock(synthetic, tmp_path):
    archive, _, _ = synthetic
    target = tmp_path / 'recovered'
    tool.restore(archive, target, PASSWORD)
    old = (target / tool.DB_NAME).read_bytes()
    # Open handle without a SQL transaction still prevents a Linux write lease.
    with open(target / tool.DB_NAME, 'rb'):
        with pytest.raises(ValueError, match='open|lease'):
            tool.restore(archive, target, PASSWORD, overwrite=True)
    lock = tmp_path / '.recovered.restore.lock'
    with lock.open('rb') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='lock'):
            tool.restore(archive, target, PASSWORD, overwrite=True)
    assert (target / tool.DB_NAME).read_bytes() == old


def test_restore_checks_foreign_keys_and_integrity(synthetic, tmp_path):
    archive, _, _ = synthetic
    encrypt, decrypt = tool.encrypt_payload, tool.decrypt_payload
    payload = decrypt(json.loads(archive.read_text()), PASSWORD)
    bad = tmp_path / 'bad.sqlite3'
    bad.write_bytes(base64.b64decode(payload['database']))
    with sqlite3.connect(bad) as db:
        db.execute("INSERT INTO period_quota_counters VALUES (99999, 'orphan', 'window', 0, 0, 0)")
    for data in (bad.read_bytes(), b'not a sqlite database'):
        payload['database'] = base64.b64encode(data).decode()
        altered = tmp_path / 'bad.json'
        altered.write_text(json.dumps(encrypt(payload, PASSWORD)))
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            tool.restore(altered, tmp_path / 'invalid', PASSWORD)
        assert not (tmp_path / 'invalid').exists()


def test_real_cli_roundtrip_synthetic_only(synthetic, tmp_path):
    _, source, _ = synthetic
    archive = tmp_path / 'cli.json'
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    # All required values and SQLite URL are synthetic and exported before the subprocess imports.
    assert environment['DATABASE_URL'].endswith(str(source))
    commands = [(['backup', '--output', str(archive)], PASSWORD + '\n' + PASSWORD + '\n'),
                (['restore', '--archive', str(archive), '--target-dir', str(tmp_path / 'cli-recovery')], PASSWORD + '\n')]
    bootstrap = ("from pydantic_settings.sources import DotEnvSettingsSource; "
                 "DotEnvSettingsSource.__call__ = lambda self: {}; "
                 "import runpy,sys; script=sys.argv.pop(1); runpy.run_path(script, run_name='__main__')")
    for arguments, stdin in commands:
        child_environment = dict(environment)
        if arguments[0] == 'restore':
            # A recovery must not require the lost source .env or its secrets.
            for key in ('ROUTER_MASTER_KEY', 'JWT_SECRET', 'ADMIN_PASSWORD', 'FINGERPRINT_SALT', 'DATABASE_URL'):
                child_environment.pop(key, None)
        completed = subprocess.run([sys.executable, '-I', '-c', bootstrap, str(SCRIPT), *arguments], input=stdin, text=True,
                                   capture_output=True, env=child_environment, timeout=30)
        assert completed.returncode == 0, completed.stderr
        assert 'verified' in completed.stdout
        assert 'synthetic-provider-secret' not in completed.stdout + completed.stderr
    assert table_data(source) == table_data(tmp_path / 'cli-recovery' / tool.DB_NAME)


def test_wrong_effective_master_key_refuses_backup(synthetic, tmp_path, monkeypatch):
    monkeypatch.setenv('ROUTER_MASTER_KEY', Fernet.generate_key().decode())
    output = tmp_path / 'wrong-master.json'
    with pytest.raises(Exception):
        tool.backup(output, PASSWORD)
    assert not output.exists()


def test_atomic_restore_refuses_target_created_during_preparation(synthetic, tmp_path, monkeypatch):
    archive, _, _ = synthetic
    target = tmp_path / 'race'
    original = tool.ensure_offline
    calls = 0
    def racing(path):
        nonlocal calls
        original(path)
        calls += 1
        if calls == 2:
            target.mkdir(mode=0o700)
            (target / 'sentinel').write_text('synthetic-existing-data')
    monkeypatch.setattr(tool, 'ensure_offline', racing)
    with pytest.raises(OSError):
        tool.restore(archive, target, PASSWORD)
    assert (target / 'sentinel').read_text() == 'synthetic-existing-data'
    assert not (target / tool.DB_NAME).exists()


def test_running_target_process_is_refused(synthetic, tmp_path):
    archive, _, _ = synthetic
    target = tmp_path / 'running'
    tool.restore(archive, target, PASSWORD)
    # Synchronize on stdout, not a guessed delay; the synthetic process has entered target cwd.
    process = subprocess.Popen([sys.executable, '-I', '-c', "import time; print('ready', flush=True); time.sleep(20)"],
                               cwd=target, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'ready'
        with pytest.raises(ValueError, match='running process'):
            tool.restore(archive, target, PASSWORD, overwrite=True)
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_racing_database_open_aborts_before_replacement(synthetic, tmp_path, monkeypatch):
    from contextlib import contextmanager
    import time
    archive, _, _ = synthetic
    target = tmp_path / 'lease-race'
    tool.restore(archive, target, PASSWORD)
    old = (target / tool.DB_NAME).read_bytes()
    original_lease, original_offline = tool.exclusive_lease, tool.ensure_offline
    leases = []
    processes = []
    @contextmanager
    def observed_lease(path):
        with original_lease(path) as fd:
            leases.append(fd)
            yield fd
    calls = 0
    def racing(path):
        nonlocal calls
        original_offline(path)
        calls += 1
        if calls == 2:
            process = subprocess.Popen([sys.executable, '-I', '-c',
                                        "import sys; print('opening', flush=True); f=open(sys.argv[1],'rb'); f.close()",
                                        str(target / tool.DB_NAME)], stdout=subprocess.PIPE, text=True)
            processes.append(process)
            assert process.stdout.readline().strip() == 'opening'
            deadline = time.monotonic() + 5
            while fcntl.fcntl(leases[-1], fcntl.F_GETLEASE) == fcntl.F_WRLCK:
                assert time.monotonic() < deadline, 'Reader never reached the leased inode'
                time.sleep(0.005)
            assert process.poll() is None  # The real kernel lease blocks the open.
    monkeypatch.setattr(tool, 'exclusive_lease', observed_lease)
    monkeypatch.setattr(tool, 'ensure_offline', racing)
    try:
        with pytest.raises(ValueError, match='lease'):
            tool.restore(archive, target, PASSWORD, overwrite=True)
    finally:
        for process in processes:
            process.wait(timeout=5)
    assert (target / tool.DB_NAME).read_bytes() == old
    assert not list(tmp_path.glob('lease-race.before-*'))

