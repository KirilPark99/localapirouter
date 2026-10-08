# Full encrypted instance backup and offline recovery

`backend/scripts/instance_backup.py` is separate from the UI's provider export.
It backs up the **entire SQLite database** through SQLite's backup API, including
committed WAL pages: admin users, providers/credentials/proxies, models and
preferences, routing/Fusion/Judge profiles, router-key policies, period counters
and reservations, settings/security/compression, logs, usage, cache and migration
tables. It does not migrate, start the application, call models or contact providers.

The password-encrypted archive also contains every effective application Settings
value, including `ROUTER_MASTER_KEY`, JWT/auth/admin settings, fingerprint salt and
native OAuth secrets. The Settings loader follows the same environment-over-dotenv
precedence as the application. Run backup with the **same exported environment as
the instance**; `--env-file` selects an alternative dotenv file but does not override
exported variables. A wrong master key refuses backup if stored encrypted fields
cannot be decrypted. Do not generate replacement secrets during recovery.

The CLI never reads another process's secrets and cannot infer an environment
which only your service manager knows. Supply that same environment through your
normal service-manager/launcher workflow. Do not paste it into commands or logs.

## Backup (no restart required)

From the project root, in the instance's configured environment:

```sh
cd /home/kiril/PythonProjects/MyAIrouter
umask 077
mkdir -p "$HOME/.local/state/MyAIrouter/backups"
backend/.venv/bin/python -I backend/scripts/instance_backup.py backup \
  --output "$HOME/.local/state/MyAIrouter/backups/full-20261007.json"
```

The CLI prompts twice for a password of at least 12 characters; it is not placed
in argv, shell history or output. An existing archive is never overwritten.
Expected success output:

```text
Encrypted full-instance backup created; SQLite integrity/FKs verified.
```

Optional explicit dotenv source:

```sh
backend/.venv/bin/python -I backend/scripts/instance_backup.py backup \
  --env-file /absolute/private/path/instance.env \
  --output "$HOME/.local/state/MyAIrouter/backups/full-another-name.json"
```

Store the password separately. Archives and snapshot files are mode `0600`;
temporary directories are private. Encryption uses the existing BackupService
pattern: PBKDF2-HMAC-SHA256 (100,000 iterations, random 16-byte salt) and
 authenticated Fernet. Full-instance and provider-export archive types are distinct;
existing provider exports/imports remain unchanged. Archives contain all historical
rows, possibly including request content when enabled; never attach them to reports.

## Offline restore into a separate recovery directory

Restore works even if the old `.env` and its secrets are lost. Use the same code
version and installed dependencies which produced the backup.

```sh
cd /home/kiril/PythonProjects/MyAIrouter
umask 077
backend/.venv/bin/python -I backend/scripts/instance_backup.py restore \
  --archive "$HOME/.local/state/MyAIrouter/backups/full-20261007.json" \
  --target-dir "$HOME/.local/state/MyAIrouter/recovery-20261007"
```

Expected success output:

```text
Offline recovery bundle restored; SQLite integrity/FKs and settings verified.
```

The bundle contains `instance.sqlite3` and private `effective-settings.json`.
The restored `DATABASE_URL` points at that bundle's database; all other effective
settings are preserved. **No live `.env`, application configuration, or database
inside the code checkout is replaced.** Recovery is not deployment and does not
start anything. Only the caller-chosen recovery directory can be written.

An existing target requires `--overwrite`, must be a private owner-only recovery
bundle from this CLI, and must contain no WAL/SHM or other files. Successful
replacement preserves the complete previous bundle beside it as
`recovery-20261007.before-<random-id>`; the directory exchange is atomic. On a
failed exchange, a private staged candidate may remain at that pathname; the
original target remains intact. Never delete these directories until you have
identified which bundle you need.

```sh
backend/.venv/bin/python -I backend/scripts/instance_backup.py restore \
  --archive "$HOME/.local/state/MyAIrouter/backups/full-20261007.json" \
  --target-dir "$HOME/.local/state/MyAIrouter/recovery-20261007" --overwrite
```

Restore is **Linux-only and fail-closed** when required kernel/filesystem features
are unavailable. It uses a nonblocking per-target flock, `/proc` cwd/open-handle
checks, and mandatory inode write leases on both old and new database files.
Any existing DB handle prevents replacement, even without a SQL transaction and
when `/proc` cannot inspect an undumpable process. Concurrent opens block during
publication; new-directory restore uses atomic no-replace, existing-directory
restore uses atomic exchange. A running target process, another restore, wrong
password, modified ciphertext, invalid integrity/FKs/credentials, parent traversal,
symlink path or unsupported archive member refuses recovery. Do not bypass these
checks by copying the main DB file or deleting WAL/SHM files.

## Deliberate cutover, only in an authorized maintenance window

The CLI deliberately has no live-install command. Stop the actual service using
its deployment manager, verify all workers are gone, then configure its launcher
to load **all** values in the private restored JSON into its environment before
starting. Merely pointing `DATABASE_URL` at the recovered DB with fresh master/JWT/
fingerprint values is not a full recovery.

For an explicitly approved foreground launch, the following loads the restored
JSON without printing any settings and runs the existing installed uvicorn. Do
not run it while production8007 is still serving. Change the recovery pathname
only; the host/port remain the restored values.

```sh
backend/.venv/bin/python -I -c 'import json,os,sys; from pathlib import Path; p=Path(sys.argv[1]); s=json.loads(p.read_text()); os.environ.update({k:str(v).lower() if isinstance(v,bool) else str(v) for k,v in s.items()}); os.execv(sys.executable,[sys.executable,"-m","uvicorn","app.main:app","--app-dir","backend","--host",str(s["HOST"]),"--port",str(s["PORT"])])' \
  "$HOME/.local/state/MyAIrouter/recovery-20261007/effective-settings.json"
```

This is a real application startup, not part of restore validation. It may run the
application's normal lifecycle; approve that separately and follow the project's
normal migration/version runbook. Do not restart the current service merely to
verify this feature. Keep the old DB/environment for rollback and verify auth,
credential decryption, profiles and counters before accepting the cutover.

## Isolated checks

All tests use synthetic SQLite/.env data, disable repository dotenv, and never
start application lifespan or contact providers:

```sh
LINGLING_TEST_RUN=instance-cache-20261007-final \
  backend/.venv/bin/python -I \
  /home/kiril/.local/state/MyAIrouter/lingling-20261006/run_tests.py \
  backend/tests/test_instance_backup.py backend/tests/test_cache_lifecycle.py
```

The real CLI subprocess is exercised for backup → restore, including recovery
without any source secrets exported. Tests compare every table, verify committed
WAL rows and master-key decryption, preserved auth/fingerprint settings, permissions,
profiles and quota counters, and assert rejection/no-clobber boundaries.

## Response-cache settings

`RESPONSE_CACHE_TTL_SECONDS` defaults to `3600`, must be positive and finite.
`RESPONSE_CACHE_MAX_BYTES` defaults to `67108864` (64 MiB), must be a positive
integer. Configure only during a separately authorized configuration change;
this implementation does not edit live settings. The cache's default TTL is finite
on both RAM/SQLite paths; non-expiring legacy entries are misses. L1 eviction counts
UTF-8 response/signature bytes plus Python object/LRU overhead, not only entry count.
Oversized responses remain eligible for TTL-bounded SQLite storage, never retained
in L1. Metrics expose `l1_memory_bytes`, `l1_max_bytes`, and `ttl_seconds`.

The byte budget is conservative retained-entry accounting, **not a cap on total
process RSS** or temporary serialization/DB-driver allocations. The full backup
CLI also holds the encrypted/base64 payload in RAM; for multi-gigabyte databases,
a streaming archive format is a separate change, not an untested promise here.
