"""Run inside an isolated test container, never against a real Surf data directory.

Starts a localhost web fixture, pairs a disposable client, changes the dashboard,
and checks Chromium navigation, identity and pairing persistence across restart.
"""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

UI = "http://127.0.0.1:18081"
TLS = "https://127.0.0.1:18080/api/v1/"
HOME = Path(os.environ.get("SURF_HOME", "/data/surf"))
authorization = "Basic " + base64.b64encode(("admin:" + os.environ["DASHBOARD_PASSWORD"]).encode()).decode()


def request(url, body=None, authenticated=True, origin=UI):
    headers = {"X-Surf-UI": "1", "Origin": origin, "Content-Type": "application/json"}
    if authenticated:
        headers["Authorization"] = authorization
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    with urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=6) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def ready():
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            state = request(UI + "/api/state")
            if state["ready"]:
                return state
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise AssertionError("Surf did not become ready")


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><title>Home Assistant fixture</title><h1>Dashboard fixture</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
threading.Thread(target=fixture.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{fixture.server_port}/dashboard-tablet/0"
state = ready()
identity = state["server"]["serverID"]
for path in ("/", "/api/state"):
    try:
        request(UI + path, authenticated=False)
        raise AssertionError("Unauthenticated administration allowed")
    except urllib.error.HTTPError as error:
        assert error.code == 401
try:
    request(UI + "/api/pair", {}, origin="https://untrusted.example")
    raise AssertionError("Cross-origin administration allowed")
except urllib.error.HTTPError as error:
    assert error.code == 403
print("PASS: setup authentication and CSRF protection")

# Use a real RSA public key in the same DER format as the iOS client.
with tempfile.TemporaryDirectory() as temporary:
    public_keys = []
    for index in range(2):
        key = str(Path(temporary) / f"key-{index}.pem")
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", key],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        public_keys.append(subprocess.check_output(["openssl", "pkey", "-in", key, "-pubout", "-outform", "DER"]))
pairing = request(UI + "/api/pair", {})
client = {"deviceName": "Disposable smoke-test iPad", "publicKey": base64.urlsafe_b64encode(public_keys[0]).decode().rstrip("="), "code": pairing["code"]}
candidate = request(TLS + "pairing/request", client, authenticated=False)
assert len(candidate["phrase"].split()) == 6
ui_candidate = request(UI + "/api/state")["candidates"][0]
assert ui_candidate["phrase"] == candidate["phrase"]
try:
    request(TLS + "pairing/request", {**client, "publicKey": base64.urlsafe_b64encode(public_keys[1]).decode().rstrip("=")}, authenticated=False)
    raise AssertionError("Pairing code could be reused")
except urllib.error.HTTPError as error:
    assert error.code == 403
paired = request(TLS + "pairing/confirm/" + candidate["id"], {}, authenticated=False)
assert paired["paired"]
print("PASS: real TLS pairing, single-use code, matching six-word phrase")

descriptor_before = json.loads((HOME / "daemon.json").read_text())
request(UI + "/api/settings", {"dashboard_url": url, "public_address": "192.168.1.50:18080", "adaptive_video": True})
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        descriptor = json.loads((HOME / "daemon.json").read_text())
        if descriptor["adminToken"] != descriptor_before["adminToken"]:
            state = ready()
            break
    except (OSError, json.JSONDecodeError):
        pass
    time.sleep(1)
else:
    raise AssertionError("Settings did not restart Surf")
assert state["server"]["serverID"] == identity
assert any(device["id"] == paired["deviceID"] for device in state["devices"])
assert state["settings"]["dashboard_url"] == url
print("PASS: dashboard settings restart preserves server identity and paired device")

deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    debug_port = int((HOME / "profile/DevToolsActivePort").read_text().splitlines()[0])
    targets = request(f"http://127.0.0.1:{debug_port}/json/list", authenticated=False)
    if any(target.get("url") == url and target.get("title") == "Home Assistant fixture" for target in targets):
        break
    time.sleep(1)
else:
    raise AssertionError("Chromium did not load the dashboard fixture over loopback")
print("PASS: Chromium renders the localhost dashboard fixture in host mode")
request(UI + "/api/revoke", {"id": paired["deviceID"]})
assert not any(device["id"] == paired["deviceID"] for device in request(UI + "/api/state")["devices"])
request(UI + "/api/pair/cancel", {})
print("PASS: device revocation and pairing cancellation")
fixture.shutdown()
fixture.server_close()
