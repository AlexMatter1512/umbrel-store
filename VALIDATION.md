# Validation — 2026-10-04

Validated locally in Docker Desktop's ARM64 Linux VM, with additional amd64
container tests under emulation for package `0.17.0-4`:

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
- Confirmed the previous startup script loses `HOME=/data` when `gosu` switches
  to numeric UID 1000, assigning the unwritable `/` instead.
- Corrected startup sets HOME and persistent XDG config/cache directories after
  dropping privileges. The smoke test checks the running service's environment
  and directory ownership, rather than Docker exec's separate environment.
- ARM64 and emulated amd64 smoke tests pass with the correction, including native
  pairing, backend restart, identity persistence, device revocation and logs.
- amd64 Chromium creates its Crash Reports database in the writable config
  directory. The precise reported Crashpad failure was not reproduced locally;
  the old amd64 startup encountered a transient capture-extension failure.

No custom front end or website-specific behavior remains. Surf uses its upstream browsing defaults.

Limits: native amd64 hardware, installation on the target Umbrel, and streaming to the physical iOS device have not been tested locally. The package provides native web management and headless streaming; Surf's local Browser setup action still requires a desktop session. Updates to the packaged root-owned host executable are managed through Umbrel.
