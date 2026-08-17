#!/usr/bin/env sh
set -eu

PIPER_HTTP_HOST="${PIPER_HTTP_HOST:-0.0.0.0}"
PIPER_HTTP_PORT="${PIPER_HTTP_PORT:-8995}"
PIPER_VOICE_DIR="${PIPER_VOICE_DIR:-/voices}"
PIPER_PRELOAD_VOICE_DIR="${PIPER_PRELOAD_VOICE_DIR:-/opt/piper/preloaded-voices}"
PIPER_DEFAULT_VOICE="${PIPER_DEFAULT_VOICE:-en_US-lessac-medium}"
PIPER_TIMEOUT_SECONDS="${PIPER_TIMEOUT_SECONDS:-60}"
PIPER_SERVER_EXTRA_ARGS="${PIPER_SERVER_EXTRA_ARGS:-}"

mkdir -p "${PIPER_VOICE_DIR}" /tmp/piper-http

if [ -d "${PIPER_PRELOAD_VOICE_DIR}" ]; then
  for model in "${PIPER_PRELOAD_VOICE_DIR}"/*.onnx; do
    [ -f "${model}" ] || continue
    model_name="$(basename "${model}")"
    if [ ! -f "${PIPER_VOICE_DIR}/${model_name}" ]; then
      cp "${PIPER_PRELOAD_VOICE_DIR}/${model_name}" "${PIPER_VOICE_DIR}/${model_name}"
    fi
    if [ -f "${PIPER_PRELOAD_VOICE_DIR}/${model_name}.json" ] && [ ! -f "${PIPER_VOICE_DIR}/${model_name}.json" ]; then
      cp "${PIPER_PRELOAD_VOICE_DIR}/${model_name}.json" "${PIPER_VOICE_DIR}/${model_name}.json"
    fi
  done
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

case "${PIPER_HTTP_PORT}" in
  ''|*[!0-9]*)
    echo "PIPER_HTTP_PORT must be numeric (got: ${PIPER_HTTP_PORT})" >&2
    exit 2
    ;;
esac

case "${PIPER_TIMEOUT_SECONDS}" in
  ''|*[!0-9]*)
    echo "PIPER_TIMEOUT_SECONDS must be numeric (got: ${PIPER_TIMEOUT_SECONDS})" >&2
    exit 2
    ;;
esac

# shellcheck disable=SC2086
exec python3 /usr/local/bin/piper-http-server.py ${PIPER_SERVER_EXTRA_ARGS}
