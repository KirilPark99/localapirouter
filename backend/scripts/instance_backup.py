#!/usr/bin/env python3
"""Full encrypted SQLite recovery bundles. No app startup, migrations or network calls."""
import argparse
import base64
from contextlib import ExitStack, contextmanager, closing
import ctypes
import errno
import fcntl
import getpass
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.dont_write_bytecode = True
TYPE = 'myairouter_full_instance'
DB_NAME = 'instance.sqlite3'
SETTINGS_NAME = 'effective-settings.json'


def safe_path(value):
    path = Path(value).absolute()
    if '..' in path.parts:
        raise ValueError('Parent traversal is not accepted')
    if any(part.is_symlink() for part in [path, *path.parents]):
        raise ValueError('Symlink paths are not accepted')
    return path


def private_write(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())


def validate_sqlite(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite foreign key check failed')


# Same authenticated Fernet/PBKDF2 pattern as BackupService, without its ORM/global engine imports.
def _cipher(password, salt):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    if not isinstance(password, str) or len(password.strip()) < 12:
        raise ValueError('Backup password must contain at least 12 characters')
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.strip().encode())))


def encrypt_payload(payload, password):
    salt = os.urandom(16)
    return {'type': TYPE, 'version': 1, 'encrypted': True, 'salt': base64.b64encode(salt).decode(),
            'ciphertext': _cipher(password, salt).encrypt(json.dumps(payload, ensure_ascii=False).encode()).decode()}


def decrypt_payload(envelope, password):
    if (not isinstance(envelope, dict) or set(envelope) != {'type', 'version', 'encrypted', 'salt', 'ciphertext'}
            or envelope['type'] != TYPE or type(envelope['version']) is not int or envelope['version'] != 1
            or envelope['encrypted'] is not True):
        raise ValueError('Unsupported encrypted full-instance archive')
    try:
        salt = base64.b64decode(envelope['salt'], validate=True)
        if len(salt) != 16:
            raise ValueError('Invalid salt')
        return json.loads(_cipher(password, salt).decrypt(envelope['ciphertext'].encode()))
    except Exception:
        raise ValueError('Incorrect password or corrupted encrypted archive') from None


def validate_secrets(path, values):
    # Preserve the application's legacy master-key compatibility (core.crypto.get_fernet).
    import hashlib
    from cryptography.fernet import Fernet
    key = values['ROUTER_MASTER_KEY'].strip().encode()
    try:
        cipher = Fernet(key)
    except ValueError:
        cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(key).digest()))
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            quoted = '"' + table.replace('"', '""') + '"'
            for column in db.execute('PRAGMA table_info(' + quoted + ')').fetchall():
                if column[1].startswith('encrypted_'):
                    field = '"' + column[1].replace('"', '""') + '"'
                    for (token,) in db.execute('SELECT ' + field + ' FROM ' + quoted):
                        if token:
                            cipher.decrypt(token.encode())


def settings_class(bootstrap=None):
    # config.py instantiates global settings on import. Restore must also work on a
    # fresh checkout without .env; bootstrap only this CLI process, never a live file.
    saved = dict(os.environ)
    try:
        if bootstrap is not None:
            for key in ('ROUTER_MASTER_KEY', 'JWT_SECRET', 'ADMIN_PASSWORD', 'FINGERPRINT_SALT'):
                os.environ[key] = bootstrap[key]
            os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
        from app.core.config import Settings
        return Settings
    finally:
        os.environ.clear()
        os.environ.update(saved)


def effective_settings(env_file=None):
    if env_file is not None:
        from dotenv import dotenv_values
        dotenv = dotenv_values(env_file)
        bootstrap = {key: os.environ.get(key, dotenv.get(key)) for key in
                     ('ROUTER_MASTER_KEY', 'JWT_SECRET', 'ADMIN_PASSWORD', 'FINGERPRINT_SALT')}
        Settings = settings_class(bootstrap)
    else:
        Settings = settings_class()
    from pydantic import SecretStr
    current = Settings(_env_file=env_file) if env_file is not None else Settings()
    return {key: value.get_secret_value() if isinstance(value, SecretStr) else value
            for key, value in current.model_dump().items()}


def backup(output, password, *, env_file=None):
    output = safe_path(output)
    values = effective_settings(env_file)
    from sqlalchemy.engine import make_url
    url = make_url(values['DATABASE_URL'])
    if url.get_backend_name() != 'sqlite' or not url.database or url.database == ':memory:':
        raise ValueError('A file-backed SQLite DATABASE_URL is required')
    source = safe_path(url.database)
    if not source.is_file():
        raise ValueError('Source SQLite database does not exist')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='.instance-backup-', dir=output.parent) as work:
        snapshot = Path(work) / DB_NAME
        private_write(snapshot, b'')
        # SQLite's backup API includes committed WAL pages, unlike copying the main file.
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original, closing(sqlite3.connect(snapshot)) as destination:
            original.backup(destination)
            destination.execute('PRAGMA journal_mode=DELETE')
        validate_sqlite(snapshot)
        validate_secrets(snapshot, values)
        payload = {'type': TYPE, 'version': 1, 'settings': values,
                   'database': base64.b64encode(snapshot.read_bytes()).decode('ascii')}
        archive = Path(work) / 'archive.json'
        private_write(archive, json.dumps(encrypt_payload(payload, password)).encode())
        # link is an atomic, no-clobber publication on the same filesystem.
        os.link(archive, output)
        directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return output


def ensure_offline(target):
    if not Path('/proc/self/fd').is_dir():
        raise ValueError('Offline verification requires Linux /proc')
    for process in Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue  # Private owner-only bundle; other users cannot enter it.
            cwd = (process / 'cwd').resolve(strict=True)
            if cwd == target or target in cwd.parents:
                raise ValueError('Target instance has a running process')
            for fd in (process / 'fd').iterdir():
                try:
                    opened = fd.resolve(strict=True)
                except FileNotFoundError:
                    continue
                if opened == target or target in opened.parents:
                    raise ValueError('Target instance has open files')
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            # Undumpable same-UID processes hide /proc handles. The mandatory inode
            # write lease below still rejects ANY open DB, independently of /proc visibility.
            continue


@contextmanager
def exclusive_lease(path):
    # Linux inode write leases close the scan->replace race: concurrent opens block.
    # ponytail: Linux-only offline recovery; fail closed elsewhere instead of weak heuristics.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    previous = signal.signal(signal.SIGIO, signal.SIG_IGN)
    acquired = False
    try:
        try:
            fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_WRLCK)
            acquired = True
        except OSError:
            raise ValueError('Target database is open or write leases are unavailable') from None
        yield fd
        if fcntl.fcntl(fd, fcntl.F_GETLEASE) != fcntl.F_WRLCK:
            raise ValueError('Offline database lease was interrupted')
    finally:
        if acquired:
            fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_UNLCK)
        os.close(fd)
        signal.signal(signal.SIGIO, previous)


def exchange_directories(first, second):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None or rename(-100, os.fsencode(first), -100, os.fsencode(second), 2) != 0:
        raise OSError(ctypes.get_errno() or errno.ENOSYS, 'Atomic directory exchange unavailable')


def restore(archive, target, password, *, overwrite=False):
    archive, target = safe_path(archive), safe_path(target)
    # Never write settings or DB inside this running code checkout. Recover alongside it.
    if target == ROOT or ROOT in target.parents or target in ROOT.parents:
        raise ValueError('Restore must target a separate recovery directory, not the code checkout')
    payload = decrypt_payload(json.loads(archive.read_text()), password)
    if (not isinstance(payload, dict) or set(payload) != {'type', 'version', 'settings', 'database'}
            or payload['type'] != TYPE or type(payload['version']) is not int or payload['version'] != 1):
        raise ValueError('Unsupported full-instance archive')
    from pydantic import SecretStr
    if not isinstance(payload['settings'], dict):
        raise ValueError('Invalid archive settings')
    Settings = settings_class(payload['settings'])
    if not isinstance(payload['settings'], dict) or set(payload['settings']) != set(Settings.model_fields):
        raise ValueError('Archive settings do not match this application version')
    checked = Settings(_env_file=None, **payload['settings'])
    values = {key: value.get_secret_value() if isinstance(value, SecretStr) else value
              for key, value in checked.model_dump().items()}
    database = base64.b64decode(payload['database'], validate=True)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = target.parent / ('.' + target.name + '.restore.lock')
    with os.fdopen(os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'rb') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another restore holds the target lock') from None
        exists = target.exists()
        if exists and not overwrite:
            raise ValueError('Existing target requires --overwrite; old bundle will be preserved')
        if exists:
            # Only previously restored owner-private bundles may be overwritten.
            if (not target.is_dir() or target.stat().st_uid != os.getuid() or target.stat().st_mode & 0o077
                    or set(item.name for item in target.iterdir()) != {DB_NAME, SETTINGS_NAME}):
                raise ValueError('Overwrite requires a private recovery bundle without SQLite sidecars')
        ensure_offline(target)
        with tempfile.TemporaryDirectory(prefix='.instance-restore-', dir=target.parent) as work:
            staged = Path(work) / 'bundle'
            staged.mkdir(mode=0o700)
            db_path = staged / DB_NAME
            private_write(db_path, database)
            validate_sqlite(db_path)
            validate_secrets(db_path, values)
            values['DATABASE_URL'] = 'sqlite+aiosqlite:///' + str(target / DB_NAME)
            private_write(staged / SETTINGS_NAME, json.dumps(values, ensure_ascii=False).encode())
            with ExitStack() as stack:
                leases = [stack.enter_context(exclusive_lease(db_path))]
                if exists:
                    leases.append(stack.enter_context(exclusive_lease(target / DB_NAME)))
                ensure_offline(target)
                if any(fcntl.fcntl(fd, fcntl.F_GETLEASE) != fcntl.F_WRLCK for fd in leases):
                    raise ValueError('Concurrent database open interrupted the offline lease')
                if exists:
                    # Put the staged bundle at its durable preservation pathname first:
                    # one atomic exchange then leaves the old bundle outside temp cleanup.
                    preserved = target.with_name(target.name + '.before-' + uuid.uuid4().hex)
                    staged.rename(preserved)
                    exchange_directories(preserved, target)
                    # On failure leave the private candidate intact; never risk deleting an old DB.
                else:
                    # Linux renameat2 NOREPLACE rejects targets created during preparation.
                    libc = ctypes.CDLL(None, use_errno=True)
                    rename = getattr(libc, 'renameat2', None)
                    if rename is None or rename(-100, os.fsencode(staged), -100, os.fsencode(target), 1) != 0:
                        raise OSError(ctypes.get_errno() or errno.ENOSYS, 'Atomic no-clobber restore unavailable')
            directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    # Read back the exact publication, without logging any row or secret value.
    validate_sqlite(target / DB_NAME)
    if json.loads((target / SETTINGS_NAME).read_text()) != values:
        raise ValueError('Restored settings verification failed')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('backup')
    create.add_argument('--output', required=True)
    create.add_argument('--env-file', help='Settings dotenv file (exported environment takes precedence)')
    recover = commands.add_parser('restore')
    recover.add_argument('--archive', required=True)
    recover.add_argument('--target-dir', required=True)
    recover.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    password = getpass.getpass('Backup password (at least 12 characters): ')
    try:
        if args.command == 'backup':
            if password != getpass.getpass('Confirm backup password: '):
                raise ValueError('Passwords do not match')
            backup(args.output, password, env_file=args.env_file)
            print('Encrypted full-instance backup created; SQLite integrity/FKs verified.')
        else:
            restore(args.archive, args.target_dir, password, overwrite=args.overwrite)
            print('Offline recovery bundle restored; SQLite integrity/FKs and settings verified.')
    except Exception as error:
        # Config/SQL exceptions may contain secrets: print class only, never exception bodies.
        print('Operation refused or failed (' + type(error).__name__ + '). No live settings were changed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
