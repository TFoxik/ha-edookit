#!/usr/bin/env bash
# Run a local Home Assistant with this integration loaded from the working copy.
#
#   scripts/dev-ha.sh start     set up config/ (first run) and start HA in the background
#   scripts/dev-ha.sh stop      stop it
#   scripts/dev-ha.sh restart   stop + start, e.g. after editing the integration
#   scripts/dev-ha.sh status    is it running, and is the web UI answering
#   scripts/dev-ha.sh logs      follow the HA log (Ctrl+C stops following, not HA)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT/config"
HASS="$ROOT/.venv/bin/hass"
PID_FILE="$CONFIG/hass.pid"
OUT_FILE="$CONFIG/hass.out"
LOG_FILE="$CONFIG/home-assistant.log"
URL="http://localhost:8123"

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

setup() {
  if [[ ! -x "$HASS" ]]; then
    echo "No Home Assistant in $ROOT/.venv - set up the venv first (see README, Development)." >&2
    exit 1
  fi

  mkdir -p "$CONFIG/custom_components"
  local link="$CONFIG/custom_components/edookit"
  if [[ ! -e "$link" ]]; then
    ln -s ../../custom_components/edookit "$link"
    echo "Linked custom_components/edookit into config/."
  fi

  if [[ ! -f "$CONFIG/configuration.yaml" ]]; then
    cat > "$CONFIG/configuration.yaml" <<'EOF'
# default_config minus bluetooth: macOS kills a Home Assistant started
# without Bluetooth permission (e.g. from the Claude desktop app) as soon as
# the bluetooth integration touches CoreBluetooth.
frontend:
config:
history:
logbook:
energy:
sun:
zone:
my:
backup:
conversation:
media_source:
image_upload:
webhook:
mobile_app:

# A dev instance with a real account in it has no business on the LAN.
http:
  server_host: 127.0.0.1

logger:
  default: info
  logs:
    custom_components.edookit: debug
    pyedookit: debug
EOF
    echo "Wrote config/configuration.yaml with debug logging for the integration."
  fi
}

start() {
  if is_running; then
    echo "Already running (pid $(cat "$PID_FILE")) at $URL"
    return
  fi
  setup
  nohup "$HASS" -c "$CONFIG" >"$OUT_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "Started Home Assistant (pid $!)."
  echo "The first start installs the frontend and can take several minutes."
  echo -n "Waiting for $URL "
  for _ in $(seq 1 300); do
    if ! is_running; then
      echo
      echo "Home Assistant exited during startup. Last output:" >&2
      tail -n 30 "$OUT_FILE" >&2
      rm -f "$PID_FILE"
      exit 1
    fi
    if curl -fs -o /dev/null "$URL"; then
      echo
      echo "Ready: open $URL"
      return
    fi
    echo -n "."
    sleep 2
  done
  echo
  echo "Still starting after 10 minutes; it keeps going in the background. Check: $0 logs"
}

stop() {
  if ! is_running; then
    echo "Not running."
    rm -f "$PID_FILE"
    return
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid"
  echo -n "Stopping (pid $pid) "
  for _ in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo
      echo "Stopped."
      return
    fi
    echo -n "."
    sleep 1
  done
  echo
  echo "Did not stop within 30s, killing it."
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
}

status() {
  if is_running; then
    echo "Running (pid $(cat "$PID_FILE"))."
    if curl -fs -o /dev/null "$URL"; then
      echo "Web UI is up at $URL"
    else
      echo "Web UI not answering yet (still starting?)."
    fi
  else
    echo "Not running."
  fi
}

logs() {
  if [[ ! -f "$LOG_FILE" ]]; then
    echo "No log yet at $LOG_FILE - showing startup output instead."
    exec tail -f "$OUT_FILE"
  fi
  exec tail -f "$LOG_FILE"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) logs ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}" >&2
    exit 2
    ;;
esac
