#!/usr/bin/env bash
# Прогон сервера через MCP Inspector CLI (протокол 2026-07-28) с сохранением лога.
# Использование: bash inspector/run_inspector.sh
# Переменная INSPECTOR позволяет указать локальную копию CLI вместо npx.
set -u
cd "$(dirname "$0")/.."
LOG=inspector/inspector_log.txt
PORT=8765
URL="http://127.0.0.1:$PORT/mcp"
INSPECTOR=${INSPECTOR:-"npx -y @modelcontextprotocol/inspector@2.10.1 --cli"}

rm -f /tmp/consult_state.json
CONSULT_STATE_FILE=/tmp/consult_state.json PYTHONPATH=. .venv/bin/python -m consult_mcp.server --http --port $PORT \
  > inspector/server_stderr.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT
sleep 3

run() {
  echo "\$ inspector $*" | tee -a "$LOG"
  $INSPECTOR "$URL" "$@" 2>&1 | tee -a "$LOG"
  echo "[exit code: ${PIPESTATUS[0]}]" | tee -a "$LOG"
  echo | tee -a "$LOG"
}

: > "$LOG"
echo "# MCP Inspector $(date -u +%Y-%m-%dT%H:%M:%SZ), server: consult_mcp (MCP 2026-07-28, stateless HTTP)" | tee -a "$LOG"
echo | tee -a "$LOG"

M="--protocol-era modern"
run $M --method tools/list --strict
# успех и ошибка для каждого инструмента
run $M --method tools/call --tool-name consult_search_slots --tool-arg date=2026-10-14 topic=homework
run $M --method tools/call --tool-name consult_search_slots --tool-arg date=14.10.2026 format=zoom
run $M --method tools/call --tool-name consult_get_slot --tool-arg slot_id=s-1014-iva-1030 response_format=detailed
run $M --method tools/call --tool-name consult_get_slot --tool-arg slot_id=s-0101-xyz-0900
run $M --method tools/call --tool-name consult_book --tool-args-json \
  '{"slot_id":"s-1014-iva-1030","student_id":"st-1001","topic":"homework","idempotency_key":"inspector-0001"}'
run $M --method tools/call --tool-name consult_book --tool-args-json \
  '{"slot_id":"s-1014-iva-1030","student_id":"st-1001","topic":"project","idempotency_key":"inspector-0002"}'
run $M --method tools/call --tool-name consult_list_bookings --tool-arg student_id=st-1001
run $M --method tools/call --tool-name consult_list_bookings --tool-arg student_id=1001
BID=$(python3 -c "import json;print(next(iter(json.load(open('/tmp/consult_state.json'))['bookings'])) ['booking_id'])" 2>/dev/null)
run $M --method tools/call --tool-name consult_get_booking --tool-arg booking_id=$BID student_id=st-1001
run $M --method tools/call --tool-name consult_get_booking --tool-arg booking_id=$BID student_id=st-2002
run $M --method tools/call --tool-name consult_cancel --tool-arg booking_id=$BID student_id=st-1001
run $M --method tools/call --tool-name consult_cancel --tool-arg booking_id=$BID student_id=st-1001
# старая эра (initialize) должна быть отклонена
run --protocol-era legacy --method tools/list
