# Validation — 2026-10-04

Passed locally using Docker Desktop's ARM64 Linux VM:

- Docker image build with the official Surf 0.17.0 ARM64 release and a verified archive checksum.
- Chromium 154.0.8037.92 installed from Debian's repository; Surf selected system Chromium successfully.
- Headless Surf startup, native TLS listener, Bonjour advertisement and embedded iOS client bundle.
- Actual `network_mode: host`, ordinary container privileges, 1 GiB shared memory and UID 1000 ownership of Surf data.
- Six setup-server tests: authentication, CSRF, URL validation, private persistent settings, pairing API delegation and TLS fingerprint rejection before sending the control token.
- Real TLS pairing with a generated RSA device key, a matching six-word phrase and rejection of invitation reuse by another key.
- Dashboard settings save restarted the actual Surf process and preserved both its identity and the test paired device.
- Chromium loaded and rendered a local HTTP dashboard fixture through loopback.
- Device revocation and pairing cancellation.
- Full container restart retained the identity and settings and returned a healthy backend.
- Compose parsing, shell and JavaScript syntax checks.
- The pinned public base image manifest includes linux/amd64 and linux/arm64.
- Umbrel's current source confirms package files are copied to APP_DATA_DIR, host networking is supported, and deterministic app credentials are displayed by the UI.

Limits: the amd64 runtime has not been executed locally. The package has not been installed on the target Umbrel, connected to the physical iPad, or authenticated against the user's actual Home Assistant. The localhost fixture verifies browser routing and navigation, not end-to-end iPad video/audio quality. First-start provisioning downloads dependencies rather than using an already-published custom image.
