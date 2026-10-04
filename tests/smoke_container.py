"""Run as UID 1000, only inside a fresh disposable Surf test container."""
import base64
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

UI = "http://127.0.0.1:18081"
TLS = "https://127.0.0.1:18080/api/v1/"
HOME = Path(os.environ.get("SURF_HOME", "/data/surf"))


def request(url, body=None, origin=UI, raw=False):
    headers = {"X-Surf-Desktop": "1", "Origin": origin, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    with urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=6) as response:
        payload = response.read()
        return payload if raw else json.loads(payload) if payload else {}


def ready():
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            request(UI + "/api/status")
            return request(UI + "/api/backend/api/v1/server")
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise AssertionError("Surf did not become ready")


# Check the service's real environment, not docker exec's inherited HOME.
assert os.geteuid() == 1000, "Run with docker exec -u 1000:1000"
service = next(path for path in Path("/proc").iterdir()
               if path.name.isdigit() and (path / "cmdline").exists()
               and b"/opt/surf-umbrel/proxy.py" in (path / "cmdline").read_bytes().split(b"\0"))
environment = dict(item.split(b"=", 1) for item in (service / "environ").read_bytes().split(b"\0") if b"=" in item)
assert service.stat().st_uid == 1000
assert environment[b"HOME"] == b"/data"
for variable in (b"XDG_CONFIG_HOME", b"XDG_CACHE_HOME"):
    directory = Path(os.fsdecode(environment[variable]))
    assert directory.is_relative_to(HOME) and directory.is_dir()
    assert directory.stat().st_uid == 1000
print("PASS: unprivileged Surf service has persistent writable home/config/cache directories")

state = ready()
identity = state["serverID"]
private_ui = json.loads((HOME / "desktop-instance.json").read_text())["url"]
html = request(UI + "/", raw=True)
assert html == request(private_ui + "/", raw=True)
assert b'id="pairing-code"' in html
print("PASS: original Surf HTML is forwarded byte for byte")

for path in ("/", "/api/config", "/api/backend/api/v1/admin/devices"):
    response = urllib.request.urlopen(UI + path, timeout=6)
    assert response.status == 200
    assert response.headers.get("WWW-Authenticate") is None
    response.close()
try:
    request(UI + "/api/restart", {}, origin="https://untrusted.example")
    raise AssertionError("Cross-origin administration allowed")
except urllib.error.HTTPError as error:
    assert error.code == 403
print("PASS: interface/API open without login; cross-origin mutations rejected")

with tempfile.TemporaryDirectory() as temporary:
    public_keys = []
    for index in range(2):
        key = str(Path(temporary) / f"key-{index}.pem")
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", key],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        public_keys.append(subprocess.check_output(["openssl", "pkey", "-in", key, "-pubout", "-outform", "DER"]))
pairing = request(UI + "/api/backend/api/v1/admin/pairing/session", {"publicAddress": "192.0.2.10:18080"})
client = {"deviceName": "Disposable smoke-test client", "publicKey": base64.urlsafe_b64encode(public_keys[0]).decode().rstrip("="), "code": pairing["code"]}
candidate = request(TLS + "pairing/request", client)
assert len(candidate["phrase"].split()) == 6
ui_candidates = request(UI + "/api/backend/api/v1/admin/pairing/candidates")["candidates"]
assert any(item["phrase"] == candidate["phrase"] for item in ui_candidates)
try:
    request(TLS + "pairing/request", {**client, "publicKey": base64.urlsafe_b64encode(public_keys[1]).decode().rstrip("=")})
    raise AssertionError("Pairing code could be reused by another client")
except urllib.error.HTTPError as error:
    assert error.code == 403
paired = request(TLS + "pairing/confirm/" + candidate["id"], {})
assert paired["paired"]
print("PASS: native pairing, QR payload, single-use code and verification phrase")
assert pairing.get("qrPNG")

before = json.loads((HOME / "daemon.json").read_text())["adminToken"]
request(UI + "/api/restart", {})
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        current = json.loads((HOME / "daemon.json").read_text())
        if current["adminToken"] != before:
            assert ready()["serverID"] == identity
            break
    except (OSError, json.JSONDecodeError):
        pass
    time.sleep(1)
else:
    raise AssertionError("Native restart did not restart the backend")
devices_url = UI + "/api/backend/api/v1/admin/devices"
assert any(device["id"] == paired["deviceID"] for device in request(devices_url)["devices"])
print("PASS: native restart preserves identity and paired device")
request(UI + "/api/backend/api/v1/admin/devices/revoke/" + paired["deviceID"], {})
assert not any(device["id"] == paired["deviceID"] for device in request(devices_url)["devices"])
req = urllib.request.Request(UI + "/api/backend/api/v1/admin/pairing/session", method="DELETE",
                             headers={"X-Surf-Desktop": "1", "Origin": UI})
with urllib.request.urlopen(req, timeout=5) as response:
    assert response.status == 204
assert request(UI + "/api/backend/api/v1/admin/logs/sources")
print("PASS: native device revocation, pairing cancellation and log API")
