#!/bin/sh
set -eu

NODE_EXPORTER_ADDR="${NODE_EXPORTER_ADDR:-:9100}"
APP_ADDR="${APP_ADDR:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"

node_exporter --web.listen-address="${NODE_EXPORTER_ADDR}" &

exec python -m uvicorn timiniprint.app.web:app \
  --host "${APP_ADDR}" \
  --port "${APP_PORT}" \
  --log-level info \
  --access-log
