# SurrealDB Operations Guide

> SurrealDB 3.0 · Open Notebook project · macOS / Linux

---

## Table of Contents

1. [Installation](#installation)
2. [Starting SurrealDB](#starting-surrealdb)
3. [Stopping SurrealDB](#stopping-surrealdb)
4. [Restarting SurrealDB](#restarting-surrealdb)
5. [Health Check](#health-check)
6. [SQL REPL — Interactive Shell](#sql-repl--interactive-shell)
7. [Surreal Studio — Web UI](#surreal-studio--web-ui)
8. [Export & Backup](#export--backup)
9. [Import & Restore](#import--restore)
10. [CLI Command Reference](#cli-command-reference)
11. [Environment Variables](#environment-variables)
12. [Homebrew Service (auto-start)](#homebrew-service-auto-start)
13. [Docker](#docker)
14. [Open Notebook Cheat Sheet](#open-notebook-cheat-sheet)
15. [Troubleshooting](#troubleshooting)

---

## Installation

### Option A — Homebrew (macOS, recommended for local dev)

```bash
brew install surrealdb/tap/surreal
surreal version     # → 3.0.0 for macos on aarch64
```

### Option B — Official install script (macOS / Linux)

```bash
curl -sSf https://install.surrealdb.com | sh
```

### Option C — Docker (no local install required)

```bash
docker pull surrealdb/surrealdb:v2   # project uses v2-compatible SQL
```

> **Version note for Open Notebook**: The project was written for SurrealDB v2.
> If you install v3 via Homebrew, two migration syntax changes apply — see
> [Troubleshooting](#troubleshooting).

---

## Starting SurrealDB

### Development — in-memory (data lost on exit)

Fastest for quick testing; no files written.

```bash
surreal start memory \
  --user root --pass root \
  --bind 0.0.0.0:8000 \
  --log info
```

### Development — persisted with RocksDB (recommended for Open Notebook)

Data is written to disk and survives restarts.

```bash
surreal start \
  --user root --pass root \
  --bind 0.0.0.0:8000 \
  --log info \
  rocksdb:/path/to/data/database.db
```

**Open Notebook default** (matches the `.env` file):

```bash
surreal start \
  --user root --pass root \
  --bind 0.0.0.0:8000 \
  --log info \
  rocksdb:/Users/ghu/aiworker/open-notebook/surreal_data/database.db
```

### Background (nohup)

```bash
nohup surreal start \
  --user root --pass root \
  --bind 0.0.0.0:8000 \
  --log info \
  rocksdb:./surreal_data/database.db \
  > /tmp/surrealdb.log 2>&1 &

echo "SurrealDB PID: $!"
```

### With logging to file

```bash
surreal start \
  --user root --pass root \
  --bind 0.0.0.0:8000 \
  --log info \
  --log-file-enabled \
  --log-file-path ./logs \
  --log-file-name surrealdb.log \
  --log-file-rotation daily \
  rocksdb:./surreal_data/database.db
```

### Strict security (production)

```bash
surreal start \
  --user root --pass "$(openssl rand -base64 32)" \
  --bind 127.0.0.1:8000 \
  --log warn \
  --deny-all \
  rocksdb:./surreal_data/database.db
```

---

## Stopping SurrealDB

### If started in foreground

Press `Ctrl + C`.

### If started in background with nohup / &

```bash
# Find the process
pgrep -la surreal

# Kill gracefully
pkill -TERM surreal

# Confirm it stopped
pgrep surreal || echo "stopped"
```

### Kill by PID (if you saved it)

```bash
kill -TERM $SURREALDB_PID
```

### Force kill (last resort — may corrupt data)

```bash
pkill -9 surreal
```

---

## Restarting SurrealDB

```bash
pkill -TERM surreal
sleep 2

# Check it's fully stopped
pgrep surreal || echo "ready to restart"

# Start again
nohup surreal start \
  --user root --pass root \
  --bind 0.0.0.0:8000 \
  --log info \
  rocksdb:./surreal_data/database.db \
  > /tmp/surrealdb.log 2>&1 &

echo "Restarted, PID: $!"
```

---

## Health Check

### HTTP health endpoint

```bash
curl http://localhost:8000/health
# → (empty 200 OK means healthy)

# Get version info
curl http://localhost:8000/version
# → surrealdb-3.0.0+...
```

### Via CLI

```bash
surreal is-ready --endpoint http://localhost:8000
# → OK (exit 0) or error (exit 1)
```

### Verify with credentials

```bash
echo 'INFO FOR ROOT;' | surreal sql \
  --endpoint ws://localhost:8000 \
  --username root \
  --password root \
  --hide-welcome
```

---

## SQL REPL — Interactive Shell

The REPL lets you run SurrealQL directly against the database.

### Connect (root level — all namespaces and databases)

```bash
surreal sql \
  --endpoint ws://localhost:8000 \
  --username root \
  --password root
```

### Connect scoped to Open Notebook database

```bash
surreal sql \
  --endpoint ws://localhost:8000 \
  --username root \
  --password root \
  --namespace open_notebook \
  --database open_notebook
```

### Pretty-printed JSON output

```bash
surreal sql \
  --endpoint ws://localhost:8000 \
  --username root \
  --password root \
  --namespace open_notebook \
  --database open_notebook \
  --pretty
```

### Run a single query without entering REPL

```bash
echo 'USE NS open_notebook DB open_notebook; SELECT * FROM notebook LIMIT 5;' \
  | surreal sql \
    --endpoint ws://localhost:8000 \
    --username root --password root \
    --pretty
```

### Pipe a SurrealQL file

```bash
surreal sql \
  --endpoint ws://localhost:8000 \
  --username root --password root \
  < my_queries.surql
```

### Common REPL commands

Once inside the REPL:

```sql
-- Switch namespace and database
USE NS open_notebook DB open_notebook;

-- List all tables in current database
INFO FOR DB;

-- Show table structure
INFO FOR TABLE source;

-- Count records
SELECT count() FROM source GROUP ALL;

-- View recent notebooks
SELECT * FROM notebook ORDER BY created DESC LIMIT 10;

-- View a source and its embeddings
SELECT * FROM source:abc123;
SELECT * FROM source_embedding WHERE source = source:abc123;

-- View all chat sessions
SELECT * FROM chat_session;

-- Check migration version
SELECT * FROM _sbl_migrations ORDER BY version DESC;

-- Exit REPL
CTRL+C  (or CTRL+D)
```

---

## Surreal Studio — Web UI

SurrealDB ships with **Surreal Studio**, a built-in browser-based GUI for
querying, browsing, and managing records.

### Open Surreal Studio

With SurrealDB running, open your browser to:

```
http://localhost:8000
```

You will see the Surreal Studio login page.

### Login credentials (Open Notebook defaults)

| Field | Value |
|-------|-------|
| **Endpoint** | `http://localhost:8000` |
| **Username** | `root` |
| **Password** | `root` |
| **Namespace** | `open_notebook` |
| **Database** | `open_notebook` |

### What you can do in Surreal Studio

| Feature | How |
|---------|-----|
| Browse tables | Left sidebar → Tables |
| Run SurrealQL | Query editor (top panel) |
| View a record | Click any row in the table view |
| Create a record | `INSERT INTO table { ... }` in query editor |
| Delete a record | `DELETE table:id;` in query editor |
| Inspect indexes | `INFO FOR TABLE tablename;` |
| View DB info | `INFO FOR DB;` |
| Switch database | Namespace / Database dropdowns (top bar) |

### Using Surreal Studio for Open Notebook tables

```sql
-- Inspect schema
INFO FOR TABLE source;
INFO FOR TABLE notebook;
INFO FOR TABLE source_embedding;

-- Browse recent sources
SELECT id, title, created FROM source ORDER BY created DESC;

-- Check embedding status (should match source count)
SELECT count() FROM source GROUP ALL;
SELECT count() FROM source_embedding GROUP ALL;

-- Find notes for a notebook
SELECT * FROM artifact WHERE out = notebook:your_id;

-- Inspect migration history
SELECT * FROM _sbl_migrations;
```

---

## Export & Backup

### Export entire database to a SurrealQL file

```bash
surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  backup_$(date +%Y%m%d_%H%M%S).surql
```

### Export to stdout (pipe to gzip)

```bash
surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  - | gzip > backup_$(date +%Y%m%d).surql.gz
```

### Export only specific tables

```bash
surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  --only \
  --tables notebook,source,note \
  notebooks_and_sources.surql
```

### Export schema only (no data)

```bash
surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  --only \
  --tables false \
  schema_only.surql
```

### Scheduled backup script

```bash
#!/bin/bash
BACKUP_DIR="$HOME/surreal-backups"
mkdir -p "$BACKUP_DIR"

surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  "$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).surql"

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/*.surql | tail -n +8 | xargs rm -f
echo "Backup complete"
```

---

## Import & Restore

### Import a backup file

```bash
surreal import \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  backup_20260220.surql
```

### Import with gzip

```bash
gunzip -c backup_20260220.surql.gz | surreal sql \
  --endpoint ws://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook
```

### Run a migration script manually

```bash
surreal sql \
  --endpoint ws://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  < open_notebook/database/migrations/1.surrealql
```

### Validate a SurrealQL file before importing

```bash
surreal validate open_notebook/database/migrations/1.surrealql
# → OK (exit 0) or parse errors
```

---

## CLI Command Reference

### All top-level commands

| Command | Purpose |
|---------|---------|
| `surreal start [PATH]` | Start the database server |
| `surreal sql` | Open interactive SQL REPL |
| `surreal export` | Export database to .surql file |
| `surreal import` | Import .surql file into database |
| `surreal is-ready` | Health check (exit 0 = healthy) |
| `surreal validate <file>` | Validate a .surql file syntax |
| `surreal version` | Print CLI and server versions |
| `surreal upgrade` | Upgrade to latest stable version |
| `surreal fix` | Repair corrupt storage |

### `surreal start` key flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--bind` | `127.0.0.1:8000` | Listen address and port |
| `--user` / `-u` | — | Root username |
| `--pass` / `-p` | — | Root password |
| `--log` / `-l` | `info` | Log level: `none error warn info debug trace` |
| `--log-file-enabled` | false | Write logs to file |
| `--log-file-path` | `./logs` | Log file directory |
| `--log-file-rotation` | `daily` | Rotation: `daily hourly never` |
| `--query-timeout` | none | Max query duration |
| `--allow-all` / `-A` | — | Allow all capabilities |
| `--deny-all` / `-D` | — | Deny all capabilities (whitelist mode) |
| `--unauthenticated` | false | Skip authentication (dev only!) |

### Storage backends

| Backend | Path format | Notes |
|---------|-------------|-------|
| In-memory | `memory` | Data lost on exit; fastest |
| RocksDB | `rocksdb:/path/to/dir` | Recommended; persistent, single node |
| File | `file:/path` | Flat-file; simple but slow |
| TiKV | `tikv://host:port` | Distributed; production clusters |
| FoundationDB | `fdb://path/to/config` | Enterprise distributed |

### `surreal sql` key flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--endpoint` / `-e` | `ws://localhost:8000` | Server address |
| `--username` / `-u` | — | Username |
| `--password` / `-p` | — | Password |
| `--namespace` / `--ns` | — | Pre-select namespace |
| `--database` / `--db` | — | Pre-select database |
| `--pretty` | false | Pretty-print responses |
| `--json` | false | Emit JSON output |
| `--multi` | false | Newline = multi-line (no semicolon needed) |
| `--hide-welcome` | false | Suppress banner |

### Log levels

| Level | When to use |
|-------|-------------|
| `none` | Silence all output |
| `error` | Production — errors only |
| `warn` | Production — errors + warnings |
| `info` | Development default — standard activity |
| `debug` | Troubleshooting — verbose query details |
| `trace` | Deep debugging — very noisy |

---

## Environment Variables

All flags have `SURREAL_*` env var equivalents. Useful for `.env` files and Docker:

| Variable | Equivalent flag | Used in Open Notebook `.env` |
|----------|----------------|------------------------------|
| `SURREAL_PATH` | `start [PATH]` | — |
| `SURREAL_USER` | `--username` | `root` |
| `SURREAL_PASS` | `--password` | `root` |
| `SURREAL_BIND` | `--bind` | `0.0.0.0:8000` |
| `SURREAL_LOG` | `--log` | — |
| `SURREAL_NAMESPACE` | `--namespace` | `open_notebook` |
| `SURREAL_DATABASE` | `--database` | `open_notebook` |
| `SURREAL_NO_BANNER` | `--no-banner` | — |
| `SURREAL_LOG_FILE_ENABLED` | `--log-file-enabled` | — |

**Open Notebook `.env` section:**

```ini
SURREAL_URL=ws://localhost:8000/rpc
SURREAL_USER=root
SURREAL_PASSWORD=root
SURREAL_NAMESPACE=open_notebook
SURREAL_DATABASE=open_notebook
```

---

## Homebrew Service (auto-start)

Install SurrealDB as a macOS background service that starts automatically on boot.

### Register and start the service

```bash
brew services start surrealdb/tap/surreal
```

> The default Homebrew service uses in-memory storage on port 8000.
> For persistent data, use manual `nohup` start instead (see [Starting SurrealDB](#starting-surrealdb)).

### Check service status

```bash
brew services list | grep surreal
# surreal    started  ghu  ~/Library/LaunchAgents/surrealdb.tap.surreal.plist
```

### Stop the service

```bash
brew services stop surrealdb/tap/surreal
```

### Restart the service

```bash
brew services restart surrealdb/tap/surreal
```

### Unregister from auto-start

```bash
brew services stop surrealdb/tap/surreal
brew services deregister surrealdb/tap/surreal
```

### Custom plist for persistent data on boot (macOS)

Create `~/Library/LaunchAgents/surreal.open_notebook.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>surreal.open_notebook</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/surreal</string>
    <string>start</string>
    <string>--user</string><string>root</string>
    <string>--pass</string><string>root</string>
    <string>--bind</string><string>0.0.0.0:8000</string>
    <string>--log</string><string>info</string>
    <string>rocksdb:/Users/ghu/aiworker/open-notebook/surreal_data/database.db</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/surrealdb.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/surrealdb.log</string>
</dict>
</plist>
```

```bash
# Load
launchctl load ~/Library/LaunchAgents/surreal.open_notebook.plist

# Start
launchctl start surreal.open_notebook

# Stop
launchctl stop surreal.open_notebook

# Unload (disable auto-start)
launchctl unload ~/Library/LaunchAgents/surreal.open_notebook.plist
```

---

## Docker

### Start SurrealDB v2 (project default) with Docker

```bash
# Pull the image
docker pull surrealdb/surrealdb:v2

# Run with persistent storage
docker run -d \
  --name surrealdb \
  -p 8000:8000 \
  -v $(pwd)/surreal_data:/mydata \
  surrealdb/surrealdb:v2 \
  start --log info --user root --pass root \
  rocksdb:/mydata/database.db

# Check it started
docker logs surrealdb --tail 20
```

### Manage the Docker container

```bash
# Stop
docker stop surrealdb

# Start (resume)
docker start surrealdb

# Restart
docker restart surrealdb

# Remove (data preserved in volume)
docker rm surrealdb

# View live logs
docker logs -f surrealdb

# View health
docker inspect surrealdb | python3 -m json.tool | grep -A3 Status
```

### Via docker compose (Open Notebook)

```bash
# Start SurrealDB only
docker compose up -d surrealdb

# Stop SurrealDB
docker compose stop surrealdb

# Restart SurrealDB
docker compose restart surrealdb

# View logs
docker compose logs -f surrealdb

# Remove container (keeps volume)
docker compose rm surrealdb
```

---

## Open Notebook Cheat Sheet

All commands below use the Open Notebook defaults (`open_notebook` namespace and database, `root`/`root` credentials).

### Quick connect alias

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
alias surreal-on='surreal sql \
  --endpoint ws://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  --pretty'
```

Then just run: `surreal-on`

### Start the full stack (manual)

```bash
# 1. SurrealDB
nohup surreal start --user root --pass root --bind 0.0.0.0:8000 --log info \
  rocksdb:./surreal_data/database.db > /tmp/surrealdb.log 2>&1 &

# 2. API (waits for DB then runs migrations automatically)
nohup uv run --env-file .env run_api.py > /tmp/open-notebook-api.log 2>&1 &

# 3. Worker
nohup uv run --env-file .env surreal-commands-worker \
  --import-modules commands > /tmp/open-notebook-worker.log 2>&1 &

# 4. Frontend
npm --prefix frontend run dev > /tmp/open-notebook-frontend.log 2>&1 &
```

### Stop the full stack

```bash
pkill -f "next dev" 2>/dev/null
pkill -f "surreal-commands-worker" 2>/dev/null
pkill -f "run_api.py" 2>/dev/null
pkill -TERM surreal 2>/dev/null
```

### Inspect Open Notebook data

```bash
echo 'USE NS open_notebook DB open_notebook;

-- Summary counts
SELECT count() FROM notebook GROUP ALL;
SELECT count() FROM source GROUP ALL;
SELECT count() FROM note GROUP ALL;
SELECT count() FROM source_embedding GROUP ALL;
SELECT count() FROM chat_session GROUP ALL;

-- Migration version
SELECT version FROM _sbl_migrations ORDER BY version DESC LIMIT 1;

' | surreal sql --endpoint ws://localhost:8000 \
    --username root --password root --pretty
```

### Wipe and reset the database (destructive)

```bash
# Stop API first
pkill -f "run_api.py"

echo 'REMOVE DATABASE IF EXISTS open_notebook; REMOVE NAMESPACE IF EXISTS open_notebook;' \
  | surreal sql --endpoint ws://localhost:8000 --username root --password root

# Restart API — migrations will re-run automatically
nohup uv run --env-file .env run_api.py > /tmp/open-notebook-api.log 2>&1 &
```

### Backup Open Notebook database

```bash
surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook \
  open_notebook_backup_$(date +%Y%m%d_%H%M%S).surql
```

---

## Troubleshooting

### Port 8000 already in use

```bash
lsof -i :8000
# Kill the occupying process
kill -TERM <PID>
# Or use a different port
surreal start --bind 0.0.0.0:8001 ...
# Update .env: SURREAL_URL=ws://localhost:8001/rpc
```

### Cannot connect — connection refused

```bash
# Check if SurrealDB is running
pgrep -la surreal

# Check logs
tail -50 /tmp/surrealdb.log

# Try health endpoint
curl -v http://localhost:8000/health
```

### SurrealDB v3 migration errors (FLEXIBLE TYPE)

The project migrations were written for v2. If you installed v3 via Homebrew,
two syntax changes are required in the migration files:

| File | v2 syntax (broken) | v3 fix |
|------|--------------------|--------|
| `migrations/1.surrealql` | `FLEXIBLE TYPE option<object>` | `TYPE option<object>` |
| `migrations/7.surrealql` | `FLEXIBLE TYPE object` | `TYPE object` |
| `migrations/1.surrealql` | `SEARCH ANALYZER name BM25` | `FULLTEXT ANALYZER name BM25` |

These fixes are already applied in this codebase.

### API fails with "Failed to run database migrations"

```bash
# Check the full error
tail -50 /tmp/open-notebook-api.log

# Verify SurrealDB is accepting connections
surreal is-ready --endpoint http://localhost:8000

# Try connecting manually
echo 'SELECT 1;' | surreal sql \
  --endpoint ws://localhost:8000 \
  --username root --password root \
  --namespace open_notebook \
  --database open_notebook
```

### View what migrations have run

```bash
echo 'USE NS open_notebook DB open_notebook; SELECT * FROM _sbl_migrations;' \
  | surreal sql --endpoint ws://localhost:8000 --username root --password root --pretty
```

### Corrupt storage — repair

```bash
pkill -TERM surreal
surreal fix rocksdb:/path/to/surreal_data/database.db
# Then restart normally
```

### Check process and log tail

```bash
# Check all Open Notebook processes
pgrep -la surreal
pgrep -la "run_api"
pgrep -la "surreal-commands"
pgrep -la "next"

# Tail all logs at once
tail -f /tmp/surrealdb.log /tmp/open-notebook-api.log /tmp/open-notebook-frontend.log
```

---

*SurrealDB 3.0 · Open Notebook 1.7.4 · February 2026*
