# Surf Community Store

A community Umbrel package for [Surf](https://github.com/seg6/surf), using its **original bundled web interface and browsing defaults**.

## Install

1. Push this repository to GitHub, keeping `umbrel-app-store.yml` at the root.
2. Add its GitHub URL under **Umbrel → App Store → Community App Stores**.
3. Install **Surf** from **Surf Community Store**.
4. Wait for first-start provisioning, then open Surf in Umbrel.

The original Surf interface opens directly at `http://UMBREL_LAN_IP:18081`, without an app login or Umbrel login. Use its **Settings** to set the public address to `UMBREL_LAN_IP:18080`, then choose **Pair device** under **Paired Devices**. Scan the QR code or enter the address and code in the iOS app, compare the six words, and confirm on the device.

Browse normally in the iOS app. Surf manages tabs, bookmarks, history and website logins.

## Umbrel integration

- Unmodified Surf 0.17.0 official binary, with fixed SHA-256 checksums for linux/amd64 and linux/arm64.
- Host networking for direct LAN access and Bonjour discovery.
- Chromium, certificates, Unicode and emoji fonts.
- Surf's native desktop process provides its web interface and owns the browser/backend lifecycle.
- A small HTTP proxy exposes the private loopback interface on Umbrel's app port. It forwards native HTML, scripts, API routes and streaming logs without modifying the interface. There is no authentication layer or Umbrel app-proxy login.
- Persistent Surf data under `${APP_DATA_DIR}/data/surf`.
- Writable Chromium config and cache directories inside Surf's persistent data.
- Ordinary container privileges; Surf runs as UID/GID 1000:1000. Chromium's namespace sandbox is disabled for Docker compatibility, and shared memory is set to 1 GiB.

No custom front end, start page, browsing features or website-specific configuration is included.

The store ID `surfhome` and app ID `surfhome-surf` remain stable for upgrades; the store is named **Surf Community Store**.

## Runtime requirements

The public Python/Debian base image is digest-pinned. First startup installs Chromium and downloads verified Surf binaries, so outbound access to Debian and GitHub is required. Surf requires Chromium >=148 and can download its own verified managed browser when the installed version is older.

Normal restarts reuse installed packages. Container recreation provisions packages again, with release archives cached under `data/runtime`. The optional Dockerfile preinstalls these dependencies for faster startup.

| Port | Purpose |
| --- | --- |
| TCP 18080 | Surf's native TLS connection |
| TCP 18081 | Direct access to Surf's web interface |
| UDP 5353 | Bonjour/mDNS |

Ports 18080 and 18081 must be free. Anyone who can reach port 18081 can use Surf's management interface. Keep it on your trusted LAN. Surf's native device connection uses its own TLS and pinned server identity.

## Data and operations

Back up `data/surf` with the app stopped. It contains the identity, paired devices, desktop settings, browser profile, tabs, bookmarks, downloads and logs. Resetting the identity requires pairing again.

Upgrading from the earlier custom-page package preserves Surf data. Its old `data/settings.json` is ignored.

Docker manages startup, so leave Surf's desktop **Start at login** option off. **Browser setup** requires a visible desktop session; use the iOS app to sign into websites on this headless host. Host updates should be installed through Umbrel: the root-owned packaged executable cannot be replaced by Surf's desktop self-update installer as UID 1000.

CLI access, using the actual server container name if different:

```sh
docker exec -it -u 1000:1000 surfhome-surf_server_1 surf status
docker exec -it -u 1000:1000 surfhome-surf_server_1 surf pair
docker exec -it -u 1000:1000 surfhome-surf_server_1 surf devices list
```

If the interface reports that the backend is not running, read Surf's native startup logs:

```sh
docker exec surfhome-surf_server_1 sh -c 'tail -n 80 /data/surf/logs/desktop.log /data/surf/logs/server.log'
```

Package `0.17.0-5` delivers the `chrome_crashpad_handler: --database is required`
startup fix by setting a writable home and XDG directories after `gosu`
drops privileges. Runtime files live in `hooks/runtime/`, which Umbrel refreshes
on upgrades; the earlier top-level `runtime/` directory was only copied on
installation. Upgrade the app through Umbrel to `0.17.0-5` to apply the fix,
including when `0.17.0-4` was already installed. Existing Surf data is retained.

## Development

```sh
python3 -m unittest discover -s tests -v
APP_DATA_DIR="$PWD/surfhome-surf" docker compose -f surfhome-surf/docker-compose.yml config --quiet
docker build -t surf-umbrel:0.17.0 .
```

Run the smoke test only in a fresh disposable container, never an installed app:

```sh
docker run -d --name surf-package-test --init --network host --shm-size 1g surf-umbrel:0.17.0
docker cp tests/smoke_container.py surf-package-test:/tmp/smoke_container.py
docker exec -u 1000:1000 surf-package-test python3 /tmp/smoke_container.py
docker rm -f surf-package-test
```

Docker Desktop needs host-network support enabled. To distribute an optional prebuilt image, publish for linux/amd64 and linux/arm64 and update Compose with its public image tag and digest, retaining the runtime mount and entrypoint.

See [VALIDATION.md](VALIDATION.md) for test coverage and [Surf's documentation](https://github.com/seg6/surf/blob/v0.17.0/docs/backend.md) for native features.

This community packaging is MIT licensed. Upstream Surf's license and notices are retained in `hooks/runtime/`. This is not an official Surf or Umbrel release.
