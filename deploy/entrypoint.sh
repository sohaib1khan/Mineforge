#!/bin/sh
# Run as root briefly so /app-data is writable by the runtime UID (often the
# Bedrock UID when attaching a host data directory), then drop privileges.
set -eu

RUNTIME_UID="${MINEFORGE_RUNTIME_UID:-10001}"
RUNTIME_GID="${MINEFORGE_RUNTIME_GID:-10001}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app-data /data /tmp
  chown -R "${RUNTIME_UID}:${RUNTIME_GID}" /app-data || true
  # Do not recursively chown live world trees — only ensure config files we edit
  # are writable when the runtime UID already matches the Bedrock UID.
  for f in /data/allowlist.json /data/permissions.json /data/server.properties; do
    if [ -e "$f" ]; then
      chown "${RUNTIME_UID}:${RUNTIME_GID}" "$f" 2>/dev/null || true
    fi
  done
  # Parent /data must allow creating temp files for atomic writes.
  if [ -d /data ]; then
    chmod u+rwx /data 2>/dev/null || true
    chown "${RUNTIME_UID}:${RUNTIME_GID}" /data 2>/dev/null || true
  fi
  exec gosu "${RUNTIME_UID}:${RUNTIME_GID}" "$@"
fi

exec "$@"
