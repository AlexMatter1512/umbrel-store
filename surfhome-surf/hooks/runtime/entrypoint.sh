#!/bin/sh
set -eu
umask 077

mkdir -p /data/surf/.config /data/surf/.cache /data/surf/runtime/ublock-origin-lite
chown 1000:1000 /data /data/surf /data/surf/.config /data/surf/.cache \
  /data/surf/runtime /data/surf/runtime/ublock-origin-lite

# Seed Surf's writable extension cache from the image, without downloads.
# Existing browser profiles, pairing records and identity stay in /data/surf.
for extension in /opt/surf-resources/ublock-origin-lite/*; do
  destination="/data/surf/runtime/ublock-origin-lite/$(basename "$extension")"
  if [ ! -f "$destination/manifest.json" ]; then
    mkdir -p "$destination"
    cp -a "$extension/." "$destination/"
    chown -R 1000:1000 "$destination"
  fi
done

# gosu resets HOME for a numeric UID; set it after dropping privileges.
exec gosu 1000:1000 env HOME=/data \
  XDG_CONFIG_HOME=/data/surf/.config XDG_CACHE_HOME=/data/surf/.cache \
  python3 /opt/surf-umbrel/proxy.py
