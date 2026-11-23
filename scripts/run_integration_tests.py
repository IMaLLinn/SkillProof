"""Start a real FastAPI server against a temporary DB and run frontend-backend integration tests."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def load_passed_test_ids():
    target = Path(__file__).resolve().with_name("run_frontend_tests.py")
    spec = importlib.util.spec_from_file_location("run_frontend_tests", target)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.passed_test_ids


def reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(base_url: str, proc: subprocess.Popen, timeout: float = 60.0) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    last_error = "not started"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Backend server exited early with code {proc.returncode}")
        try:
            with opener.open(f"{base_url}/api/health", timeout=1.0) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body == {"Status": "ok"}:
                    return
                last_error = f"Unexpected health body: {body!r}"
        except (OSError, urllib.error.URLError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(0.2)
    raise RuntimeError(f"Backend did not become healthy within {timeout:.0f}s: {last_error}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    npx = "npx.cmd" if os.name == "nt" else "npx"
    port = reserve_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    passed_test_ids = load_passed_test_ids()

    try:
        with tempfile.TemporaryDirectory(prefix="skillproof-integration-") as directory:
            temp_root = Path(directory)
            db_path = temp_root / "integration.sqlite3"
            report_path = temp_root / "vitest-integration.json"

            backend_env = os.environ.copy()
            backend_env["PYTHONPATH"] = str(root / "backend")
            backend_env["PYTHONDONTWRITEBYTECODE"] = "1"
            backend_env["SKILLPROOF_DB_PATH"] = str(db_path)
            backend_env["SKILLPROOF_ENV"] = "development"
            backend_env["SKILLPROOF_COOKIE_SECURE"] = "0"
            backend_env["SKILLPROOF_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
            backend_env["SKILLPROOF_ORIGIN"] = base_url

            frontend_env = os.environ.copy()
            for var in PROXY_VARS:
                frontend_env.pop(var, None)
            frontend_env["NO_PROXY"] = "127.0.0.1,localhost"
            frontend_env["no_proxy"] = "127.0.0.1,localhost"
            frontend_env["VITE_API_BASE"] = base_url

            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--app-dir",
                    "backend",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=root,
                env=backend_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                wait_for_health(base_url, proc)
                subprocess.run(
                    [
                        npx,
                        "vitest",
                        "run",
                        "--config",
                        "vitest.integration.config.ts",
                        "--reporter=json",
                        f"--outputFile={report_path}",
                    ],
                    cwd=root / "frontend",
                    env=frontend_env,
                    check=True,
                )
            except Exception:
                if proc.poll() is not None and proc.stdout is not None:
                    logs = proc.stdout.read()
                    if logs:
                        print(logs, file=sys.stderr)
                raise
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                if proc.stdout is not None:
                    proc.stdout.close()

            passed = passed_test_ids(json.loads(report_path.read_text(encoding="utf-8")), root)
        if not passed:
            raise ValueError("No integration tests passed")
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError, KeyError, TypeError) as error:
        print(f"Integration test run failed: {error}", file=sys.stderr)
        return 1

    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            print(f"passed_tests={json.dumps(passed)}", file=stream)
    print(f"Integration tests passed: {len(passed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
