#!/bin/sh
set -eu

# DBus: default to system bus socket path; warn if not mounted
DBUS_SYSTEM_BUS_ADDRESS="${DBUS_SYSTEM_BUS_ADDRESS:-unix:path=/run/dbus/system_bus_socket}"
export DBUS_SYSTEM_BUS_ADDRESS
_dbus_socket="${DBUS_SYSTEM_BUS_ADDRESS#unix:path=}"
if [ ! -S "${_dbus_socket}" ]; then
  echo "WARNING: DBus socket '${_dbus_socket}' not found – Bluetooth scan will not work." >&2
fi

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
