#!/bin/sh
set -eu
umask 077
export DEBIAN_FRONTEND=noninteractive

if ! command -v chromium >/dev/null 2>&1 || ! command -v gosu >/dev/null 2>&1; then
  echo 'Installing Chromium, certificates and fonts (first container start)...'
  apt-get update
  apt-get install -y --no-install-recommends chromium ca-certificates curl gosu fonts-liberation fonts-noto-color-emoji fonts-noto-core
  # Package indexes are disposable, not user data.
  apt-get clean
fi

version=0.17.0
case "$(dpkg --print-architecture)" in
  amd64) checksum=26940cc24067c368445c12aa3f59059990380109ff96ef45a358b893151d4235 ;;
  arm64) checksum=a45525acc95bceacdb4f63dd3e98f09d755900d20129ed9744c886291cb7489e ;;
  *) echo 'Surf requires an amd64 or arm64 host.' >&2; exit 1 ;;
esac
arch=$(dpkg --print-architecture)
archive="surf-${version}-linux-${arch}.tar.gz"
cache=/data/runtime
mkdir -p /data/surf
if [ "$(cat /usr/local/share/surf-version 2>/dev/null || true)" != "$version" ]; then
  mkdir -p "$cache"
  if [ ! -f "$cache/$archive" ] || ! printf '%s  %s\n' "$checksum" "$cache/$archive" | sha256sum -c - >/dev/null 2>&1; then
    echo "Downloading verified Surf $version ($arch)..."
    curl --fail --location --retry 5 --connect-timeout 20 --max-time 600 \
      "https://github.com/seg6/surf/releases/download/v${version}/${archive}" -o "$cache/$archive.part"
    printf '%s  %s\n' "$checksum" "$cache/$archive.part" | sha256sum -c -
    mv "$cache/$archive.part" "$cache/$archive"
  fi
  tar -xzf "$cache/$archive" -C "$cache"
  install -m 755 "$cache/surf-${version}-linux-${arch}/surf" /usr/local/bin/surf
  mkdir -p /usr/local/share
  printf '%s' "$version" > /usr/local/share/surf-version
fi

# Do not force an incompatible browser: Surf requires Chromium >=148 and will
# install its own SHA-256-verified managed browser if Debian's is older.
echo "Installed browser: $(chromium --version)"
chown 1000:1000 /data /data/surf
if [ "${1:-}" = '--install-only' ]; then exit 0; fi
export HOME=/data
exec gosu 1000:1000 python3 /opt/surf-umbrel/app.py
