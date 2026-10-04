import os
import urllib.request

port = os.environ.get("DASHBOARD_PORT", "18081")
with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as response:
    if response.status != 200:
        raise SystemExit(1)
