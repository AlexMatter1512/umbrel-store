"""Small authenticated setup UI and supervisor for the pinned Surf backend."""
import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
from pathlib import Path
import queue
import signal
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit

ROOT = Path(os.environ.get("DATA_DIR", "/data"))
SURF_HOME = Path(os.environ.get("SURF_HOME", str(ROOT / "surf")))
SETTINGS = ROOT / "settings.json"
DEFAULTS = {
    "dashboard_url": os.environ.get("START_URL", "http://127.0.0.1:8123/lovelace/0"),
    "public_address": "",
    "adaptive_video": True,
}
PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")


def read_settings():
    if SETTINGS.exists():
        return {**DEFAULTS, **json.loads(SETTINGS.read_text())}
    return DEFAULTS.copy()


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def validate_settings(value):
    url = value.get("dashboard_url", "")
    address = value.get("public_address", "")
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError("Enter a valid dashboard URL.")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an http:// or https:// URL without embedded credentials.")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("Invalid dashboard port.") from exc
    if not isinstance(address, str) or len(address) > 255:
        raise ValueError("Enter the Umbrel LAN address as host:18080.")
    address = address.strip()
    if address:
        target = urlsplit("//" + address)
        try:
            valid = target.hostname and target.port == int(os.environ.get("PORT", "18080"))
        except ValueError:
            valid = False
        if not valid or target.path or target.query or target.fragment or target.username or any(c.isspace() for c in address):
            raise ValueError("Use host:18080 (or the configured Surf port); no URL scheme or path.")
        if target.hostname.lower() == "localhost":
            raise ValueError("Use Umbrel's LAN address, not localhost.")
        try:
            if ipaddress.ip_address(target.hostname).is_loopback:
                raise ValueError("Use Umbrel's LAN address, not a loopback address.")
        except ValueError as exc:
            if "loopback" in str(exc):
                raise
    if type(value.get("adaptive_video")) is not bool:
        raise ValueError("Adaptive video must be true or false.")
    return {"dashboard_url": url, "public_address": address, "adaptive_video": value["adaptive_video"]}


def surf_api(path, method="GET", body=None):
    """Read the live owner descriptor; pin TLS before sending its control token."""
    descriptor = json.loads((SURF_HOME / "daemon.json").read_text())
    endpoint = urlsplit(descriptor["controlURL"])
    if endpoint.scheme != "https" or not ipaddress.ip_address(endpoint.hostname).is_loopback:
        raise ValueError("Surf control endpoint must be loopback HTTPS.")
    connection = http.client.HTTPSConnection(endpoint.hostname, endpoint.port or 443,
                                            context=ssl._create_unverified_context(), timeout=4)
    try:
        connection.connect()
        fingerprint = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
        if not hmac.compare_digest(fingerprint, descriptor["serverID"]):
            raise ValueError("Surf control certificate does not match its identity.")
        data = json.dumps(body).encode() if body is not None else None
        connection.request(method, "/api/v1/" + path, body=data,
                           headers={"X-Surf-Admin": descriptor["adminToken"], "Content-Type": "application/json"})
        response = connection.getresponse()
        payload = response.read(2 * 1024 * 1024)
        if response.status >= 400:
            raise RuntimeError(f"Surf returned HTTP {response.status}.")
        if path == "health":
            return {"ok": payload == b"ok"}
        return json.loads(payload) if payload else {}
    finally:
        connection.close()


class Supervisor:
    def __init__(self):
        self.commands = queue.Queue()
        self.stopping = threading.Event()
        self.process = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.lock = threading.Lock()

    def stop_backend(self):
        process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            surf_api("admin/shutdown", "POST", {})
        except Exception:
            process.terminate()
        try:
            process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()

    def run(self):
        while not self.stopping.is_set():
            with self.lock:
                settings = read_settings()
            environment = {**os.environ, "START_URL": settings["dashboard_url"],
                           "SURF_PUBLIC_ADDRESS": settings["public_address"],
                           "SURF_ADAPTIVE_VIDEO": "1" if settings["adaptive_video"] else "0"}
            self.process = subprocess.Popen(["surf", "serve"], env=environment, start_new_session=True)
            while not self.stopping.is_set() and self.process.poll() is None:
                try:
                    url = self.commands.get(timeout=1)
                except queue.Empty:
                    continue
                self.stop_backend()
                if url:
                    # Surf restores saved tabs before START_URL. Change the active tab
                    # only after shutdown has flushed its snapshot; preserve cookies.
                    path = SURF_HOME / "browser-session.json"
                    session = json.loads(path.read_text()) if path.exists() else {"version": 1, "tabs": [], "active": 0}
                    tabs = session.get("tabs") or [url]
                    active = min(max(session.get("active", 0), 0), len(tabs) - 1)
                    tabs[active] = url
                    session.update(tabs=tabs, active=active)
                    atomic_json(path, session)
                break
            self.stop_backend()
            if not self.stopping.is_set():
                self.stopping.wait(2)

    def save(self, settings):
        with self.lock:
            atomic_json(SETTINGS, settings)
        self.commands.put(settings["dashboard_url"])


SUPERVISOR = Supervisor()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # No request URLs, pairing codes, credentials or dashboard URLs in stdout.
        pass

    def respond(self, status, body, content_type="application/json"):
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def authorized(self):
        expected = "Basic " + base64.b64encode(("admin:" + PASSWORD).encode()).decode()
        if PASSWORD and hmac.compare_digest(self.headers.get("Authorization", ""), expected):
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Surf on Umbrel"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def do_GET(self):
        if self.path == "/healthz":
            try:
                surf_api("health")
            except Exception:
                self.respond(503, {"ok": False})
            else:
                self.respond(200, {"ok": True})
            return
        if not self.authorized():
            return
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/ui.js": ("ui.js", "text/javascript; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8")}
        if self.path in files:
            filename, content_type = files[self.path]
            self.respond(200, (Path(__file__).parent / filename).read_bytes(), content_type)
        elif self.path == "/api/state":
            with SUPERVISOR.lock:
                settings = read_settings()
            result = {"settings": settings, "ready": False, "pairing": {}, "candidates": [], "devices": []}
            try:
                result.update(server=surf_api("server"), pairing=surf_api("admin/pairing/session"),
                              candidates=surf_api("admin/pairing/candidates").get("candidates", []),
                              devices=surf_api("admin/devices").get("devices", []), ready=True)
            except Exception:
                result["message"] = "Surf is starting or restarting. Check container logs if this persists."
            self.respond(200, result)
        else:
            self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.authorized():
            return
        origin = self.headers.get("Origin")
        if self.headers.get("X-Surf-UI") != "1" or (origin and urlsplit(origin).netloc != self.headers.get("Host")):
            self.respond(403, {"error": "Use the Surf setup page for this action."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 8192:
                raise ValueError("Request is too large.")
            value = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("Expected a JSON object.")
            if self.path == "/api/settings":
                SUPERVISOR.save(validate_settings(value))
                self.respond(200, {"ok": True})
            elif self.path == "/api/pair":
                with SUPERVISOR.lock:
                    address = read_settings()["public_address"]
                if not address:
                    host = urlsplit("//" + self.headers.get("Host", "")).hostname
                    if not host:
                        raise ValueError("Set the Umbrel LAN address first.")
                    address = (f"[{host}]" if ":" in host else host) + ":" + os.environ.get("PORT", "18080")
                self.respond(200, surf_api("admin/pairing/session", "POST", {"publicAddress": address}))
            elif self.path == "/api/pair/cancel":
                self.respond(200, surf_api("admin/pairing/session", "DELETE"))
            elif self.path == "/api/revoke":
                device_id = value.get("id")
                if not isinstance(device_id, str) or not device_id or len(device_id) > 256:
                    raise ValueError("Select a device.")
                self.respond(200, surf_api("admin/devices/revoke/" + quote(device_id, safe=""), "POST", {}))
            else:
                self.respond(404, {"error": "Not found"})
        except (ValueError, TypeError) as exc:
            self.respond(400, {"error": str(exc)})
        except Exception:
            self.respond(503, {"error": "Surf is unavailable. Wait for startup, then try again."})


def main():
    if not PASSWORD:
        raise SystemExit("DASHBOARD_PASSWORD must be set; refusing to expose administration without authentication.")
    ROOT.mkdir(parents=True, exist_ok=True)
    SURF_HOME.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("DASHBOARD_PORT", "18081"))), Handler)
    server.daemon_threads = True
    SUPERVISOR.thread.start()

    def stop(signum, frame):
        SUPERVISOR.stopping.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("Surf setup page listening; use the credentials shown by Umbrel.", flush=True)
    try:
        server.serve_forever()
    finally:
        SUPERVISOR.stopping.set()
        SUPERVISOR.thread.join(timeout=30)
        server.server_close()


if __name__ == "__main__":
    main()
