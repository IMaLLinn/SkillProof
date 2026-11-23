"""Verify Ruff configuration and lint enforcement for backend and scripts."""

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LintChecksTests(unittest.TestCase):
    def test_ruff_config_enforces_layered_rules_and_fastapi_depends_allowlist(self):
        config = tomllib.loads((ROOT / "ruff.toml").read_text(encoding="utf-8"))
        lint = config["lint"]

        self.assertEqual(config["target-version"], "py313")
        self.assertEqual(lint["select"], ["E", "W", "F", "I", "B"])
        self.assertIn("E501", lint["ignore"])
        self.assertIn("fastapi.Depends", lint["flake8-bugbear"]["extend-immutable-calls"])

    def test_ruff_check_passes_on_backend_and_scripts(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "--config",
                str(ROOT / "ruff.toml"),
                str(ROOT / "backend"),
                str(ROOT / "scripts"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ruff_check_rejects_unused_import_and_allows_fastapi_depends(self):
        with tempfile.TemporaryDirectory(prefix="skillproof-ruff-") as temp_dir:
            root = Path(temp_dir)
            bad_file = root / "bad.py"
            bad_file.write_text("import json\n", encoding="utf-8")
            bad_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--no-cache",
                    "--config",
                    str(ROOT / "ruff.toml"),
                    str(bad_file),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(bad_result.returncode, 0)
            self.assertIn("F401", bad_result.stdout + bad_result.stderr)

            good_file = root / "good.py"
            long_comment = "# " + ("a" * 120)
            good_file.write_text(
                f"{long_comment}\n"
                "from fastapi import Depends\n\n\n"
                "def get_db():\n"
                "    return None\n\n\n"
                "def endpoint(con=Depends(get_db)):\n"
                "    return con\n",
                encoding="utf-8",
            )
            good_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--no-cache",
                    "--config",
                    str(ROOT / "ruff.toml"),
                    str(good_file),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(good_result.returncode, 0, good_result.stdout + good_result.stderr)
