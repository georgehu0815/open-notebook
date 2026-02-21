#!/usr/bin/env bash
# =============================================================================
# Open Notebook — Service Manager
# =============================================================================
# Usage:
#   ./scripts/services.sh <command> [service]
#
# Commands:   start | stop | restart | status | logs
# Services:   all (default) | db | api | frontend | worker
#
# Examples:
#   ./scripts/services.sh start           # start everything
#   ./scripts/services.sh start db        # start only SurrealDB
#   ./scripts/services.sh restart api     # restart only the API
#   ./scripts/services.sh stop            # stop everything
#   ./scripts/services.sh status          # show all service status
#   ./scripts/services.sh logs api        # tail the API log
# =============================================================================

# Intentionally NOT using set -e here because many helpers use exit codes
# (lsof, pgrep, kill) as boolean checks — we do explicit error handling instead.

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PID_DIR="/tmp/open-notebook"
LOG_DIR="/tmp/open-notebook"
mkdir -p "$PID_DIR"

DB_PID="$PID_DIR/db.pid"
API_PID="$PID_DIR/api.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"
WORKER_PID="$PID_DIR/worker.pid"

DB_LOG="$LOG_DIR/db.log"
API_LOG="$LOG_DIR/api.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
WORKER_LOG="$LOG_DIR/worker.log"

# ---------------------------------------------------------------------------
# SurrealDB config (native, not Docker)
# ---------------------------------------------------------------------------
SURREAL_BIN="$(command -v surreal 2>/dev/null || echo '')"
SURREAL_DATA="$ROOT/surreal_data/database.db"
SURREAL_BIND="0.0.0.0:8000"
SURREAL_USER="root"
SURREAL_PASS="root"

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $*"; }
fail() { echo -e "${RED}✗${RESET} $*"; }
info() { echo -e "${BLUE}→${RESET} $*"; }
warn() { echo -e "${YELLOW}!${RESET} $*"; }
hdr()  { echo -e "\n${BOLD}${CYAN}$*${RESET}"; }

# ---------------------------------------------------------------------------
# PID helpers
# ---------------------------------------------------------------------------

# Print running PID for a service, or empty string if not running
_read_pid() {
    local pidfile="$1"
    [ -f "$pidfile" ] || return 0
    local pid
    pid="$(cat "$pidfile")"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "$pid"
    else
        rm -f "$pidfile"
    fi
}

# Kill process tracked by PID file, then remove the file
_kill_pid() {
    local pidfile="$1"
    local label="$2"
    local pid
    pid="$(_read_pid "$pidfile")"
    if [ -z "$pid" ]; then
        info "$label: not running (no PID)"
        return 0
    fi
    info "Stopping $label (PID $pid)..."
    kill "$pid" 2>/dev/null || true
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 8 ]; do
        sleep 1
        waited=$(( waited + 1 ))
    done
    if kill -0 "$pid" 2>/dev/null; then
        warn "$label still alive after ${waited}s — sending SIGKILL"
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
    ok "$label stopped"
}

# Kill all processes matching a pattern (belt-and-suspenders cleanup)
_kill_pattern() {
    local pattern="$1"
    local label="$2"
    local pids
    pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
        warn "Killing stale $label processes: $pids"
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 1
        pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill -9 2>/dev/null || true
        fi
    fi
}

# Returns 0 if port is in use, 1 if free
_port_in_use() {
    lsof -ti :"$1" >/dev/null 2>&1
}

# Wait for a port to become available (returns 0 on success, 1 on timeout)
_wait_for_port() {
    local port="$1"
    local timeout="$2"
    local waited=0
    while ! _port_in_use "$port" && [ "$waited" -lt "$timeout" ]; do
        sleep 1
        waited=$(( waited + 1 ))
    done
    _port_in_use "$port"
}

# Wait for a port to become FREE (returns 0 when free, 1 on timeout)
_wait_port_free() {
    local port="$1"
    local timeout="$2"
    local waited=0
    while _port_in_use "$port" && [ "$waited" -lt "$timeout" ]; do
        sleep 1
        waited=$(( waited + 1 ))
    done
    ! _port_in_use "$port"
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

db_status() {
    local pid
    pid="$(_read_pid "$DB_PID")"
    if [ -n "$pid" ]; then
        echo -e "  SurrealDB  ${GREEN}running${RESET}  PID=$pid  port=8000  log=$DB_LOG"
    else
        echo -e "  SurrealDB  ${RED}stopped${RESET}"
    fi
}

db_stop() {
    _kill_pid "$DB_PID" "SurrealDB"
    _kill_pattern "surreal start" "SurrealDB"
    if ! _wait_port_free 8000 10; then
        warn "Port 8000 still in use — forcing"
        lsof -ti :8000 | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

db_start() {
    db_stop

    if [ -z "$SURREAL_BIN" ]; then
        fail "surreal not found in PATH. Install: brew install surrealdb/tap/surreal"
        return 1
    fi

    mkdir -p "$(dirname "$SURREAL_DATA")"
    info "Starting SurrealDB  →  $DB_LOG"

    nohup "$SURREAL_BIN" start \
        --user "$SURREAL_USER" \
        --pass "$SURREAL_PASS" \
        --bind "$SURREAL_BIND" \
        --log info \
        "rocksdb:$SURREAL_DATA" \
        >"$DB_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$DB_PID"

    if _wait_for_port 8000 15; then
        ok "SurrealDB started  (PID=$pid  port=8000)"
    else
        fail "SurrealDB did not open port 8000 within 15s — check $DB_LOG"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

api_status() {
    local pid
    pid="$(_read_pid "$API_PID")"
    if [ -n "$pid" ]; then
        echo -e "  API        ${GREEN}running${RESET}  PID=$pid  port=5055  log=$API_LOG"
    else
        echo -e "  API        ${RED}stopped${RESET}"
    fi
}

api_stop() {
    _kill_pid "$API_PID" "API"
    _kill_pattern "run_api.py" "API"
    _kill_pattern "uvicorn api.main:app" "API (uvicorn)"
    _wait_port_free 5055 8 || true
}

api_start() {
    api_stop

    if ! _port_in_use 8000; then
        warn "SurrealDB not on port 8000 — API may fail"
    fi

    info "Starting API  →  $API_LOG"
    cd "$ROOT"
    nohup uv run --env-file .env run_api.py >"$API_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$API_PID"

    # Wait for /health endpoint
    local waited=0 healthy=0
    while [ "$waited" -lt 20 ]; do
        sleep 1
        waited=$(( waited + 1 ))
        if curl -sf http://localhost:5055/health >/dev/null 2>&1; then
            healthy=1
            break
        fi
    done

    if [ "$healthy" -eq 1 ]; then
        ok "API started  (PID=$pid  port=5055)"
    else
        fail "API did not respond at /health within 20s — check $API_LOG"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

frontend_status() {
    local pid
    pid="$(_read_pid "$FRONTEND_PID")"
    if [ -n "$pid" ]; then
        echo -e "  Frontend   ${GREEN}running${RESET}  PID=$pid  port=3000  log=$FRONTEND_LOG"
    else
        echo -e "  Frontend   ${RED}stopped${RESET}"
    fi
}

frontend_stop() {
    _kill_pid "$FRONTEND_PID" "Frontend"
    _kill_pattern "next dev" "Frontend"
    _kill_pattern "next-server" "Frontend (next-server)"
    _wait_port_free 3000 8 || true
}

frontend_start() {
    frontend_stop

    if [ ! -d "$ROOT/frontend/node_modules" ]; then
        info "Installing frontend dependencies..."
        npm --prefix "$ROOT/frontend" install --silent
    fi

    info "Starting Frontend  →  $FRONTEND_LOG"
    cd "$ROOT"
    nohup npm --prefix "$ROOT/frontend" run dev >"$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$FRONTEND_PID"

    if _wait_for_port 3000 30; then
        ok "Frontend started  (PID=$pid  port=3000)"
    else
        fail "Frontend did not open port 3000 within 30s — check $FRONTEND_LOG"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Worker (surreal-commands-worker) — optional
# ---------------------------------------------------------------------------

worker_status() {
    local pid
    pid="$(_read_pid "$WORKER_PID")"
    if [ -n "$pid" ]; then
        echo -e "  Worker     ${GREEN}running${RESET}  PID=$pid  log=$WORKER_LOG"
    else
        echo -e "  Worker     ${RED}stopped${RESET}"
    fi
}

worker_stop() {
    _kill_pid "$WORKER_PID" "Worker"
    _kill_pattern "surreal-commands-worker" "Worker"
}

worker_start() {
    worker_stop

    info "Starting Worker  →  $WORKER_LOG"
    cd "$ROOT"
    nohup uv run --env-file .env surreal-commands-worker \
        --import-modules commands \
        >"$WORKER_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$WORKER_PID"

    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        ok "Worker started  (PID=$pid)"
    else
        fail "Worker exited immediately — check $WORKER_LOG"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Aggregate commands
# ---------------------------------------------------------------------------

cmd_status() {
    hdr "Open Notebook — Service Status"
    db_status
    api_status
    frontend_status
    worker_status
    echo ""
}

cmd_stop() {
    local svc="${1:-all}"
    hdr "Stopping: $svc"
    case "$svc" in
        all)
            frontend_stop
            worker_stop
            api_stop
            db_stop
            ;;
        db)       db_stop ;;
        api)      api_stop ;;
        frontend) frontend_stop ;;
        worker)   worker_stop ;;
        *)
            fail "Unknown service: $svc"
            usage; return 1
            ;;
    esac
    ok "Done"
}

cmd_start() {
    local svc="${1:-all}"
    hdr "Starting: $svc"
    case "$svc" in
        all)
            db_start       || return 1
            api_start      || return 1
            frontend_start || return 1
            worker_start   || return 1
            ;;
        db)       db_start       || return 1 ;;
        api)      api_start      || return 1 ;;
        frontend) frontend_start || return 1 ;;
        worker)   worker_start   || return 1 ;;
        *)
            fail "Unknown service: $svc"
            usage; return 1
            ;;
    esac
    echo ""
    cmd_status
}

cmd_restart() {
    local svc="${1:-all}"
    hdr "Restarting: $svc"
    cmd_stop  "$svc"
    echo ""
    cmd_start "$svc"
}

cmd_logs() {
    local svc="${1:-api}"
    local logfile
    case "$svc" in
        db)       logfile="$DB_LOG" ;;
        api)      logfile="$API_LOG" ;;
        frontend) logfile="$FRONTEND_LOG" ;;
        worker)   logfile="$WORKER_LOG" ;;
        *)
            fail "Unknown service: $svc  (db|api|frontend|worker)"
            return 1
            ;;
    esac
    if [ ! -f "$logfile" ]; then
        fail "Log file not found: $logfile"
        return 1
    fi
    info "Tailing $logfile  (Ctrl-C to exit)"
    tail -f "$logfile"
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF

${BOLD}Open Notebook Service Manager${RESET}

  ${CYAN}Usage:${RESET}  $0 <command> [service]

  ${CYAN}Commands:${RESET}
    start    [service]   Start services  (all if omitted)
    stop     [service]   Stop services   (all if omitted)
    restart  [service]   Stop then start
    status               Show status of all services
    logs     <service>   Tail a service log

  ${CYAN}Services:${RESET}
    all        All services (default for start/stop/restart)
    db         SurrealDB  (native rocksdb, port 8000)
    api        FastAPI backend  (port 5055)
    frontend   Next.js frontend  (port 3000)
    worker     surreal-commands background worker

  ${CYAN}Examples:${RESET}
    $0 start               # start all services
    $0 start db            # start SurrealDB only
    $0 restart db          # reboot SurrealDB
    $0 restart api         # reboot the API
    $0 stop                # stop everything
    $0 status              # show current status
    $0 logs api            # tail API log
    $0 logs db             # tail SurrealDB log
EOF
}

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
COMMAND="${1:-}"
SERVICE="${2:-all}"

cd "$ROOT"

case "$COMMAND" in
    start)   cmd_start   "$SERVICE" ;;
    stop)    cmd_stop    "$SERVICE" ;;
    restart) cmd_restart "$SERVICE" ;;
    status)  cmd_status ;;
    logs)    cmd_logs    "${2:-api}" ;;
    ""|help|--help|-h) usage ;;
    *)
        fail "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
