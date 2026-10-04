# Validation — 2026-10-04

Validated locally in Docker Desktop's ARM64 Linux VM:

- Unmodified official Surf 0.17.0 running in desktop mode without a graphical desktop.
- System Chromium 154, native TLS listener, Bonjour advertisement and embedded iOS client bundle.
- Original bundled web interface forwarded byte for byte from Surf's private loopback server.
- Interface and native management API open without credentials, with rejection of cross-origin mutations.
- Native pairing API, QR payload, matching six-word phrase, and rejection of code reuse by another client key.
- Native backend restart preserving the server identity and paired device.
- Native device revocation, pairing cancellation and log-source API through the adapter.
- Six unit tests covering unchanged HTML, access without login, CSRF, request-body forwarding, credential stripping, loopback target validation and health-response privacy.
- Compose parsing, shell syntax and whitespace checks.
- Host networking, ordinary container privileges and a 1 GiB shared-memory allowance.
- The pinned public base image supports linux/amd64 and linux/arm64.

No custom front end or website-specific behavior remains. Surf uses its upstream browsing defaults.

Limits: amd64 runtime, installation on the target Umbrel, and streaming to the physical iOS device have not been tested locally. The package provides native web management and headless streaming; Surf's local Browser setup action still requires a desktop session. Updates to the packaged root-owned host executable are managed through Umbrel.
