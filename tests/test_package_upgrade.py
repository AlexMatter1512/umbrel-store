"""Regression for Umbrel's file-copy contract during app updates."""
from pathlib import Path
import re
import shutil
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1] / "surfhome-surf"
# From getumbrel/umbrel's legacy-compat/app-script update phases. Arbitrary
# directories are copied on first install, but only these are refreshed later.
UPDATE_PATTERNS = ("docker-compose.yml", "*.template", "exports.sh", "torrc", "hooks", "umbrel-app.yml")


class PackageUpgradeTests(unittest.TestCase):
    def test_update_uses_packaged_image_and_preserves_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary)
            legacy = installed / "runtime"
            legacy.mkdir()
            for filename in ("bootstrap.sh", "proxy.py", "healthcheck.py"):
                (legacy / filename).write_text("stale installed runtime")
            data = installed / "data/surf"
            data.mkdir(parents=True)
            (data / "identity.pem").write_text("existing identity sentinel")

            for pattern in UPDATE_PATTERNS:
                for source in PACKAGE.glob(pattern):
                    destination = installed / source.name
                    if source.is_dir():
                        shutil.copytree(source, destination, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source, destination)

            compose = (installed / "docker-compose.yml").read_text()
            image = re.search(r"^\s+image:\s+(\S+)", compose, re.MULTILINE).group(1)
            self.assertRegex(image, r"^ghcr\.io/alexmatter1512/surf-umbrel:[^@]+@sha256:[0-9a-f]{64}$")
            self.assertNotIn("${APP_DATA_DIR}/runtime:", compose)
            self.assertNotIn("${APP_DATA_DIR}/hooks/runtime:", compose)
            self.assertEqual((data / "identity.pem").read_text(), "existing identity sentinel")
            self.assertEqual((legacy / "bootstrap.sh").read_text(), "stale installed runtime")


if __name__ == "__main__":
    unittest.main()
