set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_DIR}"

SINCE="${SINCE:-5m}"
TARGET="${1:-}"

if [[ -t 1 ]]; then
  RED=$'\033[31m'; YEL=$'\033[33m'; GRN=$'\033[32m'; BLD=$'\033[1m'; RST=$'\033[0m'
else
  RED=""; YEL=""; GRN=""; BLD=""; RST=""
fi

PATTERNS=(
  "DB-connection-failure|could not connect to server|psycopg2.OperationalError|connection refused|critical"
  "DNS-resolution|could not translate host name|Name or service not known|Temporary failure in name resolution|critical"
  "5xx-burst|HTTP/1\\.1\" 5[0-9][0-9]|warning"
  "restart-loop|Restarting|exit status 1|warning"
  "OOM-kill|Out of memory|Killed process|critical"
  "auth-failure|password authentication failed|JWT decode failed|warning"
)

echo "${BLD}=== Log Inspection ==="
echo "Project:   $(basename "$PROJECT_DIR")"
echo "Since:     $SINCE"
echo "Target:    ${TARGET:-(all services)}"
echo "Patterns:  ${#PATTERNS[@]}${RST}"
echo ""

if [[ -n "$TARGET" ]]; then
  LOG=$(docker compose logs --since="$SINCE" --no-color "$TARGET" 2>&1 || true)
else
  LOG=$(docker compose logs --since="$SINCE" --no-color 2>&1 || true)
fi

if [[ -z "$LOG" ]]; then
  echo "${YEL}No logs returned (is the stack running?).${RST}"
  exit 0
fi

TOTAL_HITS=0
for entry in "${PATTERNS[@]}"; do
  IFS='|' read -r name regex severity <<< "$entry"
  matches=$(echo "$LOG" | grep -E "$regex" | head -8 || true)
  count=$(echo "$LOG" | grep -cE "$regex" || true)

  if [[ "$count" -gt 0 ]]; then
    TOTAL_HITS=$((TOTAL_HITS + count))
    case "$severity" in
      critical) col="$RED" ;;
      warning)  col="$YEL" ;;
      *)        col="$GRN" ;;
    esac
    printf "%s[%s] %s — %d match(es) (%s)%s\n" "$col" "$(echo "$severity" | tr a-z A-Z)" "$name" "$count" "$severity" "$RST"
    echo "$matches" | sed 's/^/    /'
    echo ""
  fi
done

echo "${BLD}=== Container restart status ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}" \
  | awk 'NR==1 || /Restarting|unhealthy|Exited/ {print}'
echo "${RST}"

if [[ $TOTAL_HITS -eq 0 ]]; then
  echo "${GRN}OK — no known failure patterns matched in the last $SINCE.${RST}"
  exit 0
else
  echo "${RED}${BLD}ALERT — $TOTAL_HITS log-pattern hits matched. Investigate the highlighted services.${RST}"
  exit 1
fi
