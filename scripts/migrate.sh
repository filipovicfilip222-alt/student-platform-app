#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# migrate.sh — Pokretanje Alembic migracija
#
# Upotreba:
#   ./scripts/migrate.sh                  — primeni sve nove migracije
#   ./scripts/migrate.sh revision "opis"  — kreiraj novu migraciju (autogenerate)
#   ./scripts/migrate.sh downgrade -1     — rollback jednu migraciju
#   ./scripts/migrate.sh current          — prikaži trenutnu verziju šeme
#   ./scripts/migrate.sh history          — prikaži istoriju migracija
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Boje za output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ── Provera okruženja ──────────────────────────────────────────────────────────
if [ ! -f "$BACKEND_DIR/.env" ]; then
  log_error ".env fajl nije pronađen u $BACKEND_DIR"
  log_warn  "Kopiraj $BACKEND_DIR/.env.example u $BACKEND_DIR/.env i popuni vrednosti."
  exit 1
fi

if ! command -v alembic &> /dev/null; then
  log_error "alembic nije instaliran. Pokreni: pip install -r $BACKEND_DIR/requirements.txt"
  exit 1
fi

cd "$BACKEND_DIR"
source .env 2>/dev/null || true

COMMAND="${1:-upgrade}"
ARGS="${2:-head}"

case "$COMMAND" in
  upgrade)
    TARGET="${2:-head}"
    log_info "Primena migracija do: $TARGET"
    alembic upgrade "$TARGET"
    log_info "Migracije uspešno primenjene."
    ;;

  downgrade)
    TARGET="${2:--1}"
    log_warn "Rollback migracije: $TARGET"
    read -rp "Da li si siguran? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
      log_info "Otkazano."
      exit 0
    fi
    alembic downgrade "$TARGET"
    log_info "Rollback završen."
    ;;

  revision)
    MESSAGE="${2:-auto_migration}"
    log_info "Kreiranje nove migracije: $MESSAGE"
    alembic revision --autogenerate -m "$MESSAGE"
    log_info "Migracija kreirana. Proveri fajl u alembic/versions/ pre primene."
    ;;

  current)
    log_info "Trenutna verzija šeme:"
    alembic current
    ;;

  history)
    log_info "Istorija migracija:"
    alembic history --verbose
    ;;

  *)
    log_error "Nepoznata komanda: $COMMAND"
    echo ""
    echo "Dostupne komande:"
    echo "  upgrade [target]      — primeni migracije (default: head)"
    echo "  downgrade [target]    — rollback (default: -1)"
    echo "  revision \"opis\"       — kreiraj novu migraciju"
    echo "  current               — prikaži trenutnu verziju"
    echo "  history               — prikaži istoriju migracija"
    exit 1
    ;;
esac
