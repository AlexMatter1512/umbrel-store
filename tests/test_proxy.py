import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location("proxy", Path(__file__).resolve().parents[1] / "surfhome-surf/runtime/proxy.py")
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)
HTML = b"<!doctype html><title>Original Surf</title><script>nativeUi()</script>"


class NativeFixture(proxy.BaseHTTPRequestHandler):
    observed = None

    def do_GET(self):
        self.reply(HTML if self.path == "/" else b'{"native":true}')

    def do_POST(self):
        NativeFixture.observed = (self.path, dict(self.headers), self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        self.reply(b'{"native":true}')

    def reply(self, body):
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "text/html" if self.path == "/" else "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.native = proxy.ThreadingHTTPServer(("127.0.0.1", 0), NativeFixture)
        self.native_url = f"http://127.0.0.1:{self.native.server_port}"
        (Path(self.temp.name) / "desktop-instance.json").write_text(json.dumps({"url": self.native_url}))
        self.patches = [patch.object(proxy, "SURF_HOME", Path(self.temp.name))]
        for item in self.patches:
            item.start()
        self.server = proxy.ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.threads = []
        for server in (self.native, self.server):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        for server in (self.server, self.native):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join()
        for item in self.patches:
            item.stop()
        self.temp.cleanup()

    def request(self, path="/", body=None, csrf=True, origin=None, headers=None):
        headers = dict(headers or {})
        if csrf:
            headers["X-Surf-Desktop"] = "1"
        if origin:
            headers["Origin"] = origin
        req = urllib.request.Request(self.base + path, data=body, headers=headers)
        try:
            return urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as error:
            return error

    def test_serves_bundled_interface_without_changes(self):
        with self.request() as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), HTML)

    def test_page_and_native_api_open_without_login(self):
        for path in ("/", "/api/config", "/api/backend/api/v1/admin/pairing/session"):
            with self.request(path) as response:
                self.assertEqual(response.status, 200)
                self.assertIsNone(response.headers.get("WWW-Authenticate"))

    def test_csrf_rejects_cross_origin_and_missing_header(self):
        for csrf, origin in ((False, None), (True, "http://untrusted.example")):
            with self.request("/settings", b"payload", csrf=csrf, origin=origin) as response:
                self.assertEqual(response.status, 403)

    def test_forwards_native_routes_and_strips_incoming_credentials(self):
        with self.request("/settings", b"native multipart settings", origin=self.base,
                          headers={"Authorization": "Basic stale-browser-credentials"}) as response:
            self.assertEqual(response.status, 200)
        path, headers, body = NativeFixture.observed
        self.assertEqual(path, "/settings")
        self.assertEqual(body, b"native multipart settings")
        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["X-Surf-Desktop"], "1")

    def test_non_loopback_target_is_rejected(self):
        (Path(self.temp.name) / "desktop-instance.json").write_text('{"url":"http://192.168.1.1:80"}')
        with self.request() as response:
            self.assertEqual(response.status, 503)

    def test_health_does_not_expose_native_status_details(self):
        with self.request("/healthz") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"ok")


if __name__ == "__main__":
    unittest.main()
