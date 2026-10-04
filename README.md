# Surf Home — Umbrel community app store

A custom Umbrel app that runs [Surf](https://github.com/seg6/surf) in **host network mode** and streams Home Assistant to your existing Surf iPad client. This repository follows the [Umbrel community-store template](https://github.com/getumbrel/umbrel-community-app-store).

## Install on Umbrel

1. Push **this entire repository** to a GitHub repository you control. Keep `umbrel-app-store.yml` at the repository root. No Docker registry account or image publication is required.
2. In Umbrel, open **App Store → Community App Stores**, add that GitHub repository URL, and install **Surf** from **Surf Home**.
3. Allow several minutes for the first startup. It installs Chromium and fonts and downloads the checksum-verified Surf 0.17.0 release. If Debian's Chromium is below Surf's required version 148, Surf downloads its own verified managed Chromium. Setup needs outbound access to Debian, GitHub and release download servers.
4. Open Surf from Umbrel. The setup page is also at `http://UMBREL_LAN_IP:18081`. Use username **admin** and the generated password shown in Umbrel's app credentials.
5. Set **Umbrel LAN address** to `UMBREL_LAN_IP:18080` (for example `192.168.1.50:18080`). Use a DHCP reservation for a stable address.
6. Set the dashboard URL, then click **Save and open dashboard**. The default is `http://127.0.0.1:8123/lovelace/0`. For a custom dashboard use its real path, for example `http://127.0.0.1:8123/dashboard-tablet/0`.
7. Click **Create pairing code**. On your iPad, add that server address in Surf and enter the six-digit code. Compare the six words on both screens and confirm on the iPad.
8. Sign into Home Assistant **inside Surf on the iPad**, bookmark the dashboard, and enable Surf fullscreen. Surf preserves the browser profile, cookies, identity and paired devices across restarts and updates.

The iPad uses **Umbrel's LAN IP**, while the dashboard URL is resolved by **Chromium on Umbrel**. Because both Surf and [Umbrel's Home Assistant app](https://github.com/getumbrel/umbrel-apps/blob/master/home-assistant/docker-compose.yml) use host networking, `127.0.0.1:8123` reaches Home Assistant. A Home Assistant container on a different port or machine needs its corresponding URL. Surf does not require Home Assistant as an app dependency, so it can also display another local web dashboard.

## What's included

- Store ID `surfhome`, app ID `surfhome-surf`.
- Surf 0.17.0, verified against fixed SHA-256 hashes for **linux/amd64** and **linux/arm64**.
- A digest-pinned, multi-architecture Python/Debian base image, Chromium, CA certificates, Unicode and emoji fonts.
- Headless Chromium: no desktop, Xvfb, VNC, FFmpeg or PulseAudio required.
- Password-protected setup page with single-use pairing codes, six-word verification, device revocation, dashboard URL settings and adaptive video.
- A supervisor that restarts Surf if it exits and shuts it down cleanly for profile persistence.
- A 1 GiB shared-memory allowance for Chromium. No privileged mode, Docker socket, host PID namespace or host filesystem mounts.

Surf and the setup server run as UID/GID **1000:1000** after provisioning. Provisioning needs container root to install packages. Chromium runs with `CHROME_NO_SANDBOX=1` because its namespace sandbox is normally unavailable in Docker; the container still has ordinary Docker isolation. Host networking gives Surf access to services on the host.

## Ports and data

| Port | Purpose |
| --- | --- |
| TCP 18080 | Surf's native TLS connection from the iPad |
| TCP 18081 | Password-protected HTTP setup page |
| UDP 5353 | Surf Bonjour/mDNS discovery on the host network |

Ports 18080 and 18081 must be free. Permit TCP 18080 from the iPad's network. Bonjour discovery may not cross VLANs; manual pairing works when the iPad can reach the address. Use the setup page on a trusted LAN; its HTTP Basic authentication is not encrypted. Keep these ports off the public internet. Surf's native iPad connection uses its own TLS and pinned identity, so do not place Umbrel's login proxy in front of port 18080.

Everything persistent is under `${APP_DATA_DIR}/data`:

```text
settings.json           Dashboard URL, public address, adaptive video
surf/                   TLS identity, paired devices, Chromium profile,
                        browser session, bookmarks, downloads, logs
runtime/                Verified release archive cache
```

Back up the full data directory while the app is stopped. Removing `surf/identity` or resetting app data changes the identity and requires pairing again. Saving dashboard settings restarts Surf and replaces the **active tab** with the dashboard; other tabs and browser login data are retained. Home Assistant's own session expiry still applies. First launch opens the default dashboard, while ordinary restarts restore Surf's existing tabs.

## Troubleshooting

- **App is still starting:** the setup page becomes available after package provisioning. Use Umbrel's container logs to see apt/download progress. Chromium's first launch may download a managed browser.
- **Dashboard won't open:** verify Home Assistant works at `http://UMBREL_LAN_IP:8123` in a modern browser. Set the correct dashboard path. Log in using Home Assistant credentials, not the Surf setup password.
- **Pairing fails:** check TCP 18080, Wi-Fi client isolation and VLAN/firewall rules. Enter `UMBREL_LAN_IP:18080`, not `127.0.0.1`, port 8123 or port 18081. Pairings from your previous Surf host do not automatically transfer to this new host.
- **Client compatibility error:** use an iPad client compatible with Surf 0.17.0. The official host release includes the matching iOS client bundle for Surf's authenticated client-update flow.
- **Choppy stream:** adaptive video is enabled by default. Check Wi-Fi quality and CPU use on Umbrel; Chromium encodes the stream in software.

Advanced commands from an Umbrel SSH terminal:

```sh
docker exec -it -u 1000:1000 surfhome-surf_server_1 surf status
docker exec -it -u 1000:1000 surfhome-surf_server_1 surf pair
docker exec -it -u 1000:1000 surfhome-surf_server_1 surf devices list
```

Container names can vary with umbrelOS/Compose versions; find the actual name in Umbrel if needed. CLI commands inherit the same `SURF_HOME=/data/surf` as the backend.

## Development and optional prebuilt image

The default package uses a public base image and provisions dependencies once per **container creation**. Normal container restarts reuse installed packages; app upgrades/recreation install them again. Release archives remain cached on the data volume. This approach makes a new personal store usable immediately without a custom published image, at the cost of slower initial setup.

For a prebuilt image:

```sh
docker build -t surf-umbrel:0.17.0 .
```

Publish with `docker buildx build --platform linux/amd64,linux/arm64` to a registry you control, then replace `server.image` in `surfhome-surf/docker-compose.yml` with your public image tag and manifest digest. Leave the runtime bind mount and entrypoint in place. No workflow automatically publishes images or this repository.

Validate the package without installing on Umbrel:

```sh
python3 -m unittest discover -s tests -v
APP_DATA_DIR="$PWD/surfhome-surf" APP_PASSWORD=local-test-only docker compose -f surfhome-surf/docker-compose.yml config --quiet
```

See [Surf's backend documentation](https://github.com/seg6/surf/blob/v0.17.0/docs/backend.md) for protocol, browser and networking details. Upstream Surf is MIT licensed; this community packaging is also MIT licensed. This is a community package, not an official Umbrel or Surf release.

The real-container smoke test is destructive only to its disposable Surf test state. Run it in a **fresh test container**, never your installed app:

```sh
docker run -d --name surf-package-test --init --network host --shm-size 1g \
  -e DASHBOARD_PASSWORD=local-test-only surf-umbrel:0.17.0
docker cp tests/smoke_container.py surf-package-test:/tmp/smoke_container.py
docker exec surf-package-test python3 /tmp/smoke_container.py
docker rm -f surf-package-test
```

Host networking works directly on Linux. Docker Desktop needs host-network support enabled for this test. Test ports 18080 and 18081 must be free. See [VALIDATION.md](VALIDATION.md) for the checks performed here and their limits.
