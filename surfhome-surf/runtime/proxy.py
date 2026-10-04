"""HTTP adapter for Surf's unmodified bundled web interface."""
import http.client
import ipaddress
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

SURF_HOME = Path(os.environ.get("SURF_HOME", "/data/surf"))
STOPPING = threading.Event()
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailer", "transfer-encoding", "upgrade"}


def ui_endpoint():
    instance = json.loads((SURF_HOME / "desktop-instance.json").read_text())
    endpoint = urlsplit(instance["url"])
    if (endpoint.scheme != "http" or not ipaddress.ip_address(endpoint.hostname).is_loopback
            or endpoint.username or endpoint.path or endpoint.query or endpoint.fragment):
        raise ValueError("Surf's UI endpoint must be loopback HTTP.")
    return endpoint


def stop_surf(process):
    if process.poll() is not None:
        return
    connection = None
    try:
        endpoint = ui_endpoint()
        connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=4)
        connection.request("POST", "/api/quit", headers={"X-Surf-Desktop": "1"})
        connection.getresponse().read()
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        process.terminate()
    finally:
        if connection:
            connection.close()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def run_surf():
    while not STOPPING.is_set():
        # No "serve" argument: Surf's desktop process owns its bundled UI.
        process = subprocess.Popen(["surf"], start_new_session=True)
        while process.poll() is None and not STOPPING.wait(1):
            pass
        stop_surf(process)
        STOPPING.wait(2)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log credentials, pairing codes or request paths.

    def error(self, status, message):
        payload = message.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def forward(self):
        health = self.command == "GET" and self.path == "/healthz"
        if self.command != "GET":
            origin = self.headers.get("Origin")
            if (self.headers.get("X-Surf-Desktop") != "1"
                    or (origin and urlsplit(origin).netloc != self.headers.get("Host"))):
                self.error(403, "Use Surf's interface for this action.")
                return
        connection = None
        response_started = False
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if self.headers.get("Transfer-Encoding") or not 0 <= size <= 1024 * 1024:
                self.error(413, "Request is too large or uses unsupported framing.")
                return
            body = self.rfile.read(size) if size else None
            endpoint = ui_endpoint()
            connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=30)
            headers = {key: value for key, value in self.headers.items()
                       if key.lower() not in HOP_HEADERS | {"authorization", "host", "origin", "content-length"}}
            if not health:
                headers["Origin"] = f"http://{endpoint.netloc}"
            connection.request("GET" if health else self.command,
                               "/api/status" if health else self.path, body=body, headers=headers)
            response = connection.getresponse()
            if health:
                response.read()
                self.error(200 if response.status == 200 else 503, "ok" if response.status == 200 else "Surf is starting.")
                return
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in HOP_HEADERS | {"server", "date"}:
                    self.send_header(key, value)
            self.end_headers()
            response_started = True
            # Forward SSE log records immediately, without waiting for EOF.
            while chunk := response.read1(64 * 1024):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (OSError, ValueError, KeyError, http.client.HTTPException):
            if not response_started:
                self.error(503, "Surf is starting. Reload in a moment.")
        finally:
            if connection:
                connection.close()

    do_GET = forward
    do_POST = forward
    do_PUT = forward
    do_DELETE = forward


def main():
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("DASHBOARD_PORT", "18081"))), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=run_surf, daemon=True)
    worker.start()

    def stop(signum, frame):
        STOPPING.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("Serving Surf's bundled web interface on Umbrel's app port.", flush=True)
    try:
        server.serve_forever()
    finally:
        STOPPING.set()
        worker.join(timeout=35)
        server.server_close()


if __name__ == "__main__":
    main()
