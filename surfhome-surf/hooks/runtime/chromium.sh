#!/bin/sh
set -eu

# Chromium can leave Web Store verification metadata in Surf's unpacked uBOL
# cache. CDP refuses to load that reserved directory on the next browser launch.
# Strip only this generated metadata, retaining the extension and user profile.
for extension in "${SURF_HOME:-/data/surf}"/runtime/ublock-origin-lite/*; do
  [ -d "$extension" ] && [ ! -L "$extension" ] || continue
  if [ -e "$extension/_metadata" ] || [ -L "$extension/_metadata" ]; then
    rm -rf -- "$extension/_metadata"
  fi
done

exec /usr/bin/chromium "$@"
