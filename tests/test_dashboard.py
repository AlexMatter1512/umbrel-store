import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location("dashboard", Path(__file__).resolve().parents[1] / "surfhome-surf/runtime/app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Path(self.temp.name) / "settings.json"
        self.patches = [patch.object(app, "SETTINGS", self.settings), patch.object(app, "PASSWORD", "test-password")]
        for item in self.patches:
            item.start()
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        for item in self.patches:
            item.stop()
        self.temp.cleanup()

    def request(self, path, value=None, auth=True, csrf=True, origin=None):
        headers = {}
        if auth:
            headers["Authorization"] = "Basic " + base64.b64encode(b"admin:test-password").decode()
        if csrf:
            headers["X-Surf-UI"] = "1"
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(self.base + path,
                                         data=json.dumps(value).encode() if value is not None else None,
                                         headers=headers)
        try:
            return urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            return error

    def test_setup_and_pairing_state_require_password(self):
        for path in ("/", "/ui.js", "/api/state"):
            with self.request(path, auth=False) as result:
                self.assertEqual(result.status, 401)

    def test_cross_origin_or_missing_csrf_cannot_change_settings(self):
        settings = app.DEFAULTS.copy()
        for csrf, origin in ((False, None), (True, "https://untrusted.example")):
            with self.request("/api/settings", settings, csrf=csrf, origin=origin) as result:
                self.assertEqual(result.status, 403)
        self.assertFalse(self.settings.exists())

    def test_settings_are_private_persistent_and_schedule_dashboard(self):
        supervisor = app.Supervisor()
        settings = {"dashboard_url": "http://127.0.0.1:8123/dashboard-tablet/0", "public_address": "192.168.1.50:18080", "adaptive_video": True}
        with patch.object(app, "SUPERVISOR", supervisor):
            with self.request("/api/settings", settings, origin=self.base) as result:
                self.assertEqual(result.status, 200)
        self.assertEqual(json.loads(self.settings.read_text()), settings)
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)
        self.assertEqual(supervisor.commands.get_nowait(), settings["dashboard_url"])

    def test_pair_uses_lan_address_and_upstream_invitation(self):
        app.atomic_json(self.settings, {**app.DEFAULTS, "public_address": "192.168.1.50:18080"})
        with patch.object(app, "surf_api", return_value={"active": True, "code": "123456"}) as upstream:
            with self.request("/api/pair", {}) as result:
                self.assertEqual(json.load(result)["code"], "123456")
            upstream.assert_called_once_with("admin/pairing/session", "POST", {"publicAddress": "192.168.1.50:18080"})

    def test_reject_bad_urls_and_loopback_client_addresses(self):
        for url in ("file:///etc/passwd", "javascript:alert(1)", "https://user:secret@example.com", "http://host:bad"):
            with self.assertRaises(ValueError):
                app.validate_settings({**app.DEFAULTS, "dashboard_url": url})
        for address in ("127.0.0.1:18080", "localhost:18080", "192.168.1.50:8123", "http://host:18080"):
            with self.assertRaises(ValueError):
                app.validate_settings({**app.DEFAULTS, "public_address": address})

    def test_tls_identity_mismatch_never_sends_admin_token(self):
        descriptor = {"controlURL": "https://127.0.0.1:19000", "serverID": "0" * 64, "adminToken": "private"}
        connection = Mock()
        connection.sock.getpeercert.return_value = b"wrong certificate"
        with patch.object(app, "SURF_HOME", Path(self.temp.name)), patch.object(app.http.client, "HTTPSConnection", return_value=connection):
            (Path(self.temp.name) / "daemon.json").write_text(json.dumps(descriptor))
            with self.assertRaisesRegex(ValueError, "certificate"):
                app.surf_api("admin/devices")
        connection.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
