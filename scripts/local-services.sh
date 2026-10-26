#!/usr/bin/env bash
#
# Start and stop unprivileged local PostgreSQL and Redis instances for Saliksik AI.
#
# The binaries are installed into a user-owned virtual environment, so this
# script does not require sudo or system-wide services. Data lives outside the
# repository under ~/.local/share/saliksik-ai by default.
#
# Usage:
#   ./scripts/local-services.sh setup   # one-time: install pgserver + redislite
#   ./scripts/local-services.sh up      # start PostgreSQL and Redis, create dev DB
#   ./scripts/local-services.sh down    # stop both services
#   ./scripts/local-services.sh status  # show status
#
# Environment overrides:
#   SALIKSIK_DATA_DIR, SALIKSIK_SERVICES_VENV, SALIKSIK_PGDATA,
#   SALIKSIK_PGPORT, SALIKSIK_REDIS_PORT, SALIKSIK_DB_NAME,
#   SALIKSIK_DB_USER, SALIKSIK_DB_PASSWORD
#
set -euo pipefail

DATA_DIR="${SALIKSIK_DATA_DIR:-$HOME/.local/share/saliksik-ai}"
SERVICES_VENV="${SALIKSIK_SERVICES_VENV:-$DATA_DIR/services-venv}"
PGDATA="${SALIKSIK_PGDATA:-$DATA_DIR/postgres}"
PGPORT="${SALIKSIK_PGPORT:-5432}"
REDIS_PORT="${SALIKSIK_REDIS_PORT:-6379}"
REDIS_DIR="${SALIKSIK_REDIS_DIR:-$DATA_DIR/redis}"
DB_NAME="${SALIKSIK_DB_NAME:-saliksik_ai_dev}"
DB_USER="${SALIKSIK_DB_USER:-saliksik}"
DB_PASSWORD="${SALIKSIK_DB_PASSWORD:-saliksik123}"

PG_BIN=""
REDIS_SERVER=""
REDIS_CLI=""

log() {
    printf '==> %s\n' "$*"
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

find_services() {
    local pg_bin="$SERVICES_VENV/lib/python3.12/site-packages/pgserver/pginstall/bin"
    local redis_bin="$SERVICES_VENV/lib/python3.12/site-packages/redislite/bin"

    if [[ -x "$pg_bin/pg_ctl" && -x "$redis_bin/redis-server" ]]; then
        PG_BIN="$pg_bin"
        REDIS_SERVER="$redis_bin/redis-server"
        REDIS_CLI="$redis_bin/redis-cli"
        return 0
    fi

    if command -v pg_ctl >/dev/null 2>&1 && command -v redis-server >/dev/null 2>&1; then
        PG_BIN="$(dirname "$(command -v pg_ctl)")"
        REDIS_SERVER="$(command -v redis-server)"
        REDIS_CLI="$(command -v redis-cli)"
        return 0
    fi

    return 1
}

require_services() {
    if ! find_services; then
        die "local service binaries not found. Run: $0 setup"
    fi
}

setup_services() {
    command -v uv >/dev/null 2>&1 || die "uv is required. Install it from https://docs.astral.sh/uv/"
    mkdir -p "$DATA_DIR"

    if [[ ! -x "$SERVICES_VENV/bin/python" ]]; then
        log "Creating service environment at $SERVICES_VENV"
        uv venv "$SERVICES_VENV" --python 3.12
    fi

    log "Installing pgserver and redislite"
    uv pip install --python "$SERVICES_VENV/bin/python" pgserver redislite
    find_services || die "installed packages do not contain the expected binaries"
    log "Services installed"
}

start_postgres() {
    require_services

    if "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" >/dev/null 2>&1; then
        log "PostgreSQL already running on 127.0.0.1:$PGPORT"
        return 0
    fi

    mkdir -p "$DATA_DIR"
    if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
        log "Initializing PostgreSQL cluster at $PGDATA"
        "$PG_BIN/initdb" -D "$PGDATA" --auth=trust --auth-local=trust -U postgres --encoding=utf8 >/dev/null
    fi

    log "Starting PostgreSQL on 127.0.0.1:$PGPORT"
    "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$DATA_DIR/postgres.log" \
        -o "-h 127.0.0.1 -p $PGPORT -k /tmp" start >/dev/null

    for _ in $(seq 1 30); do
        if "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done
    die "PostgreSQL did not become ready; see $DATA_DIR/postgres.log"
}

ensure_database() {
    require_services

    local exists
    exists="$("$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U postgres -d postgres -tAc \
        "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null || true)"
    if [[ "$exists" != "1" ]]; then
        log "Creating PostgreSQL role '$DB_USER'"
        "$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U postgres -d postgres -v ON_ERROR_STOP=1 -c \
            "CREATE ROLE \"$DB_USER\" LOGIN PASSWORD '$DB_PASSWORD'" >/dev/null
    fi

    exists="$("$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U postgres -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null || true)"
    if [[ "$exists" != "1" ]]; then
        log "Creating database '$DB_NAME'"
        "$PG_BIN/createdb" -h 127.0.0.1 -p "$PGPORT" -U postgres -O "$DB_USER" "$DB_NAME"
    fi
}

start_redis() {
    require_services

    if "$REDIS_CLI" -h 127.0.0.1 -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        log "Redis already running on 127.0.0.1:$REDIS_PORT"
        return 0
    fi

    mkdir -p "$REDIS_DIR"
    log "Starting Redis on 127.0.0.1:$REDIS_PORT"
    "$REDIS_SERVER" --port "$REDIS_PORT" --bind 127.0.0.1 --daemonize yes \
        --dir "$REDIS_DIR" --logfile "$DATA_DIR/redis.log" --dbfilename dump.rdb

    for _ in $(seq 1 20); do
        if "$REDIS_CLI" -h 127.0.0.1 -p "$REDIS_PORT" ping >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.25
    done
    die "Redis did not become ready; see $DATA_DIR/redis.log"
}

stop_postgres() {
    if ! find_services; then
        log "PostgreSQL binaries not found; nothing to stop"
        return 0
    fi
    if "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" >/dev/null 2>&1; then
        log "Stopping PostgreSQL"
        "$PG_BIN/pg_ctl" -D "$PGDATA" -m fast stop >/dev/null
    else
        log "PostgreSQL is not running"
    fi
}

stop_redis() {
    if ! find_services; then
        log "Redis binaries not found; nothing to stop"
        return 0
    fi
    if "$REDIS_CLI" -h 127.0.0.1 -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        log "Stopping Redis"
        "$REDIS_CLI" -h 127.0.0.1 -p "$REDIS_PORT" shutdown save >/dev/null || true
    else
        log "Redis is not running"
    fi
}

show_status() {
    if ! find_services; then
        log "Services are not installed. Run: $0 setup"
        return 1
    fi

    if "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" >/dev/null 2>&1; then
        printf 'PostgreSQL: running on 127.0.0.1:%s\n' "$PGPORT"
    else
        printf 'PostgreSQL: stopped\n'
    fi

    if "$REDIS_CLI" -h 127.0.0.1 -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        printf 'Redis:      running on 127.0.0.1:%s\n' "$REDIS_PORT"
    else
        printf 'Redis:      stopped\n'
    fi
}

case "${1:-}" in
    setup)
        setup_services
        ;;
    up)
        require_services
        start_postgres
        ensure_database
        start_redis
        show_status
        ;;
    down)
        stop_redis
        stop_postgres
        ;;
    status)
        show_status
        ;;
    restart)
        stop_redis
        stop_postgres
        require_services
        start_postgres
        ensure_database
        start_redis
        show_status
        ;;
    *)
        sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
        exit 1
        ;;
esac
