set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_DIR}"

if [[ -t 1 ]]; then
  RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; RST=$'\033[0m'
else
  RED=""; GRN=""; YEL=""; RST=""
fi

ok()   { printf "  ${GRN}OK${RST}    %s\n"   "$*"; }
warn() { printf "  ${YEL}WARN${RST}  %s\n"   "$*"; }
fail() { printf "  ${RED}FAIL${RST}  %s\n"   "$*"; FAILED=$((FAILED+1)); }

FAILED=0
echo "=== SRE Microservices — pre-flight configuration validation ==="

echo ""
echo "[1/5] .env sanity"
if [[ ! -f .env ]]; then
  fail ".env not found in $PROJECT_DIR"
else
  ok   ".env exists"
  REQUIRED_KEYS=(DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD JWT_SECRET PRODUCT_SERVICE_URL GRAFANA_ADMIN_USER GRAFANA_ADMIN_PASSWORD)
  set -a
  . ./.env
  set +a
  for key in "${REQUIRED_KEYS[@]}"; do
    if [[ -z "${!key:-}" ]]; then
      fail "missing required env var: $key"
    fi
  done
  [[ $FAILED -eq 0 ]] && ok "all $((${#REQUIRED_KEYS[@]})) required env vars present"
fi

echo ""
echo "[2/5] docker-compose syntax"
if docker compose config -q 2>/tmp/compose_err; then
  ok "docker compose config — valid"
else
  fail "docker compose config failed:"
  sed 's/^/        /' /tmp/compose_err
fi

echo ""
echo "[3/5] DB_HOST DNS resolution inside the project network"
NET_NAME="$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]')_sre-net"
if ! docker network inspect "$NET_NAME" >/dev/null 2>&1; then
  warn "network $NET_NAME does not yet exist (probably stack not started). Skipping live DNS check."
else
  if docker run --rm --network "$NET_NAME" busybox:1.36 nslookup "$DB_HOST" >/tmp/nslookup 2>&1; then
    ok "DNS for DB_HOST=$DB_HOST resolves on $NET_NAME"
  else
    fail "DB_HOST=$DB_HOST does NOT resolve on $NET_NAME (this is exactly the Assignment-4 failure mode)"
    sed 's/^/        /' /tmp/nslookup
  fi
fi

echo ""
echo "[4/5] PRODUCT_SERVICE_URL targets a known service"
KNOWN_SERVICES=(auth-service product-service order-service user-service chat-service)
HOST_IN_URL=$(echo "$PRODUCT_SERVICE_URL" | sed -E 's#https?://##; s#:.*##; s#/.*##')
match=0
for s in "${KNOWN_SERVICES[@]}"; do
  [[ "$s" == "$HOST_IN_URL" ]] && match=1 && break
done
if [[ $match -eq 1 ]]; then
  ok "PRODUCT_SERVICE_URL host '$HOST_IN_URL' is a declared compose service"
else
  fail "PRODUCT_SERVICE_URL host '$HOST_IN_URL' is NOT a declared compose service"
fi

echo ""
echo "[5/5] JWT_SECRET strength"
if [[ ${#JWT_SECRET} -lt 16 ]]; then
  warn "JWT_SECRET is only ${#JWT_SECRET} chars; recommend 32+"
elif [[ "$JWT_SECRET" == *"change-me"* ]]; then
  warn "JWT_SECRET still contains the placeholder text 'change-me'"
else
  ok "JWT_SECRET length=${#JWT_SECRET}"
fi

echo ""
if [[ $FAILED -eq 0 ]]; then
  echo "${GRN}PASS${RST} — configuration validation succeeded"
  exit 0
else
  echo "${RED}FAIL${RST} — $FAILED check(s) failed; deployment blocked"
  exit 1
fi
