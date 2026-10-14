#!/bin/sh
# Build-time provisioning only. This script is removed from the final image.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends chromium ca-certificates curl gosu \
  fonts-liberation fonts-noto-color-emoji fonts-noto-core
rm -rf /var/lib/apt/lists/*

browser_major=$(/usr/bin/chromium --version | awk '{split($2, version, "."); print version[1]}')
if [ "$browser_major" -lt 148 ]; then
  echo 'Surf requires Chromium >=148; refusing to publish an incompatible image.' >&2
  exit 1
fi

version=0.17.0
arch=$(dpkg --print-architecture)
case "$arch" in
  amd64) checksum=26940cc24067c368445c12aa3f59059990380109ff96ef45a358b893151d4235 ;;
  arm64) checksum=a45525acc95bceacdb4f63dd3e98f09d755900d20129ed9744c886291cb7489e ;;
  *) echo 'Surf requires an amd64 or arm64 host.' >&2; exit 1 ;;
esac
archive="surf-${version}-linux-${arch}.tar.gz"
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
curl --fail --location --retry 5 --connect-timeout 20 --max-time 600 \
  "https://github.com/seg6/surf/releases/download/v${version}/${archive}" -o "$staging/surf.tar.gz"
printf '%s  %s\n' "$checksum" "$staging/surf.tar.gz" | sha256sum -c -
tar -xzf "$staging/surf.tar.gz" -C "$staging"
install -m 755 "$staging/surf-${version}-linux-${arch}/surf" /usr/local/bin/surf

blocker_version=2026.723.1724
curl --fail --location --retry 5 --connect-timeout 20 --max-time 600 \
  "https://github.com/uBlockOrigin/uBOL-home/releases/download/${blocker_version}/uBOLite_${blocker_version}.chromium.zip" \
  -o "$staging/ubol.zip"
printf '%s  %s\n' 363745573fe193c47793dc9233c0d1d08f54d2ed2421f3297b815d2ce13cab79 "$staging/ubol.zip" | sha256sum -c -
blocker_root="/opt/surf-resources/ublock-origin-lite/${blocker_version}"
mkdir -p "$blocker_root"
python3 -m zipfile -e "$staging/ubol.zip" "$blocker_root"
rm -rf "$blocker_root/_metadata"
