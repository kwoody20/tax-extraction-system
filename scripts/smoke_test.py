#!/usr/bin/env python3
"""
Simple smoke test:
- Verifies api_public can be imported (no module-level DB init)
- Starts a local Uvicorn server
- Checks /livez returns 200 with minimal JSON
- Checks /health returns 200 JSON (should not crash even if DB is missing)
"""

import os
import sys
import time
import json
import signal
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def http_get(url: str, timeout: float = 5.0):
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.getcode(), resp.read().decode("utf-8")


def wait_for(url: str, deadline_sec: float = 20.0):
    start = time.time()
    last_err = None
    while time.time() - start < deadline_sec:
        try:
            code, body = http_get(url, timeout=2.0)
            return code, body
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_err}")


def main():
    # 1) Import check — should not raise due to DB/env
    os.environ.setdefault("WARM_DB_ON_STARTUP", "false")
    try:
        # Ensure project root is on sys.path (script lives in scripts/)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import api_public  # noqa: F401
        print("[SMOKE] Imported api_public OK")
    except Exception as e:
        print("[SMOKE] FAILED: import api_public ->", e)
        sys.exit(1)

    # 2) Start server on a test port
    port = os.environ.get("SMOKE_PORT", "8010")
    host = "127.0.0.1"
    env = os.environ.copy()
    # Ensure DB warmup is off for quick liveness
    env["WARM_DB_ON_STARTUP"] = "false"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api_public:app",
        "--host",
        host,
        "--port",
        port,
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    try:
        # 3) Wait for /livez
        url_base = f"http://{host}:{port}"
        code, body = wait_for(f"{url_base}/livez", deadline_sec=30.0)
        if code != 200:
            raise RuntimeError(f"/livez returned {code}")
        print("[SMOKE] /livez OK:", body[:120])

        # 4) /health should return JSON 200 even without DB
        # /health may include a DB timeout window (up to ~12s). Allow longer.
        code_h, body_h = http_get(f"{url_base}/health", timeout=20.0)
        if code_h != 200:
            raise RuntimeError(f"/health returned {code_h}")
        print("[SMOKE] /health OK:", body_h[:120])

        # Basic JSON validation
        json.loads(body)
        json.loads(body_h)
        print("[SMOKE] JSON responses valid")

    finally:
        # Terminate server
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass

    print("[SMOKE] PASS")


if __name__ == "__main__":
    main()
