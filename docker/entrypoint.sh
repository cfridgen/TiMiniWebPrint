#!/bin/sh
set -eu

NODE_EXPORTER_ADDR="${NODE_EXPORTER_ADDR:-:9100}"
NODE_EXPORTER_ENABLED="${NODE_EXPORTER_ENABLED:-1}"
NODE_EXPORTER_ARGS="${NODE_EXPORTER_ARGS:-}"
APP_ADDR="${APP_ADDR:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"

if [ "${NODE_EXPORTER_ENABLED}" = "1" ]; then
  # Extra args can be passed via NODE_EXPORTER_ARGS to disable noisy collectors.
  # shellcheck disable=SC2086
  node_exporter --web.listen-address="${NODE_EXPORTER_ADDR}" ${NODE_EXPORTER_ARGS} &
fi

exec python -m uvicorn timiniprint.app.web:app \
  --host "${APP_ADDR}" \
  --port "${APP_PORT}" \
  --log-level info \
  --access-log
