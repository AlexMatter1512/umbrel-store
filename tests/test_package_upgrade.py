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
    def test_update_replaces_active_runtime_and_preserves_data(self):
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
            runtime = re.search(r"\$\{APP_DATA_DIR\}/([^:]+):/opt/surf-umbrel:ro", compose).group(1)
            for filename in ("bootstrap.sh", "proxy.py", "healthcheck.py"):
                self.assertEqual((installed / runtime / filename).read_bytes(),
                                 (PACKAGE / runtime / filename).read_bytes())
            self.assertEqual((data / "identity.pem").read_text(), "existing identity sentinel")
            self.assertEqual((legacy / "bootstrap.sh").read_text(), "stale installed runtime")


if __name__ == "__main__":
    unittest.main()
