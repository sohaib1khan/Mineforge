#!/bin/sh
# Generate mediamtx.yml from the template (secret only via env at runtime).
set -eu

TEMPLATE="${MEDIAMTX_TEMPLATE:-/mediamtx.yml.template}"
OUT="${MEDIAMTX_CONFIG_OUT:-/tmp/mediamtx.yml}"
SECRET="${MINEFORGE_INTERNAL_STREAM_SECRET:-}"

if [ -z "$SECRET" ] || [ "$SECRET" = "CHANGE_ME_INTERNAL_STREAM_SECRET" ]; then
  echo "mediamtx: MINEFORGE_INTERNAL_STREAM_SECRET must be set to a real value" >&2
  exit 1
fi

AUTH_URL="http://mineforge:8080/internal/stream/auth?token=${SECRET}"

# Escape & in the replacement so sed does not treat it as "whole match".
ESCAPED_URL=$(printf '%s' "$AUTH_URL" | sed 's/&/\\&/g')

sed "s|__AUTH_HTTP_ADDRESS__|${ESCAPED_URL}|g" "$TEMPLATE" > "$OUT"

exec /mediamtx "$OUT"
