"""Test the CI runner and the Issue check in isolated sample directories."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
EXISTING = "test_sample.ExistingTests.test_existing"
OTHER = "test_sample.ExistingTests.test_other"
FRONTEND = "frontend/tests/sample.test.ts > Sample > passes"

spec = importlib.util.spec_from_file_location("run_frontend_tests", SCRIPTS / "run_frontend_tests.py")
frontend_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend_runner)


class QACheckTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.registrations = self.root / "tests" / "acceptance" / "issues"
        self.registrations.mkdir(parents=True)
        self.backend = self.root / "backend" / "tests"
        self.backend.mkdir(parents=True)
        self.pr = self.root / "pr.json"
        self.pr.write_text(json.dumps({"body": "Refs #7"}))
        self.changed = self.root / "changed"
        self.changed.write_bytes(b"backend/app/main.py\0")
        self.output = self.root / "output"
        self.env = {
            **os.environ,
            "PR_DETAILS": str(self.pr),
            "GITHUB_OUTPUT": str(self.output),
            "CHANGED_FILES": str(self.changed),
            "FRONTEND_RESULT": "success",
            "BACKEND_RESULT": "success",
            "PASSED_TESTS": json.dumps([EXISTING]),
            "FRONTEND_PASSED_TESTS": json.dumps([FRONTEND]),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def register(self, ids, issue=7):
        (self.registrations / f"{issue}.json").write_text(json.dumps({"required_tests": ids}))

    def run_script(self, name):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name)],
            cwd=self.root, env=self.env, capture_output=True, text=True, timeout=15,
        )

    def check(self):
        return self.run_script("check_qa.py")

    def run_tests(self, source):
        (self.backend / "test_sample.py").write_text(source)
        return self.run_script("run_backend_tests.py")

    def test_registered_test_passes_when_it_runs_successfully(self):
        result = self.run_tests(
            "import unittest\nclass ExistingTests(unittest.TestCase):\n"
            "    def test_existing(self): pass\n"
            "    @unittest.skip('skipped')\n"
            "    def test_other(self): pass\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.output.read_text()
        self.assertEqual(json.loads(output.split("=", 1)[1]), [EXISTING])
        self.env["PASSED_TESTS"] = output.split("=", 1)[1]
        self.register([EXISTING])
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 required tests", result.stdout)
        self.register([EXISTING, OTHER])
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn(OTHER, result.stderr)

    def test_required_test_must_actually_run(self):
        self.register([EXISTING, OTHER], issue=10)
        for pr_number, changed_file in ((38, "backend/app/main.py"), (41, "frontend/src/App.tsx")):
            with self.subTest(pr=pr_number, file=changed_file):
                self.pr.write_text(json.dumps({"number": pr_number, "body": "Refs #10"}))
                self.changed.write_bytes(changed_file.encode() + b"\0")
                self.env["PASSED_TESTS"] = json.dumps([EXISTING])
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"Required tests did not pass: {OTHER}", result.stderr)

                self.env["PASSED_TESTS"] = json.dumps([EXISTING, OTHER])
                result = self.check()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("2 required tests for Issues #10", result.stdout)

    def test_missing_registration_fails(self):
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Issue #7 is missing", result.stderr)

    def test_invalid_registration_fails(self):
        for ids in ([], [None], [""]):
            with self.subTest(ids=ids):
                self.register(ids)
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn("required", result.stderr)

    def test_missing_issue_reference_fails(self):
        self.pr.write_text(json.dumps({"body": "Compare with #7"}))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Issue reference", result.stderr)

    def test_multiple_issues_reuse_the_same_result(self):
        self.pr.write_text(json.dumps({"number": 99, "body": "Refs #7, #8\nCloses #9（测试）"}))
        self.register([EXISTING])
        self.register([EXISTING, OTHER], issue=8)
        self.register([OTHER], issue=9)
        self.env["PASSED_TESTS"] = json.dumps([EXISTING, OTHER])
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 required tests for Issues #7, #8, #9", result.stdout)

    def test_scrum_only_skips_registration(self):
        self.changed.write_bytes(b"docs/scrum/week7.md\0")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.changed.write_bytes(b"docs/scrum/week7.md\0backend/app/main.py\0")
        self.assertNotEqual(self.check().returncode, 0)

    def test_missing_results_fail_even_for_scrum(self):
        self.changed.write_bytes(b"docs/scrum/week7.md\0")
        self.env["PASSED_TESTS"] = ""
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Backend test results", result.stderr)

    def test_failure_outside_required_list_still_blocks(self):
        self.register([EXISTING])
        result = self.run_tests(
            "import unittest\nclass ExistingTests(unittest.TestCase):\n"
            "    def test_existing(self): pass\n"
            "    def test_other(self): self.fail('regression')\n"
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.output.exists())
        self.env["BACKEND_RESULT"] = "failure"
        self.assertNotEqual(self.check().returncode, 0)

    def test_empty_or_interrupted_discovery_fails(self):
        for source in ("", "raise SystemExit(0)\n"):
            with self.subTest(source=source):
                self.assertEqual(self.run_tests(source).returncode, 1)
                self.assertFalse(self.output.exists())

    def test_required_tests_can_span_both_layers(self):
        self.register([EXISTING, FRONTEND])
        self.changed.write_bytes(b"backend/app/main.py\0frontend/src/App.tsx\0")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 required tests", result.stdout)
        self.assertNotIn("::warning::", result.stdout + result.stderr)

    def test_invalid_or_missing_frontend_results_fail(self):
        self.changed.write_bytes(b"docs/scrum/week7.md\0")
        for results in (None, "", "[", "{}", "[]", "[null]", '[" "]'):
            with self.subTest(results=results):
                if results is None:
                    self.env.pop("FRONTEND_PASSED_TESTS", None)
                else:
                    self.env["FRONTEND_PASSED_TESTS"] = results
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn("Frontend test results", result.stderr)

    def test_test_files_must_use_designated_locations(self):
        self.register([EXISTING])
        self.changed.write_bytes(b"backend/tests/test_x.py\0frontend/tests/a/b.test.tsx\0")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

        misplaced = (
            "frontend/src/foo.test.ts", "tests/e2e/a.spec.ts", "backend/app/test_x.py",
            "backend/tests/nested/test_x.py", "backend/tests/x_test.py", "frontend/tests/a.spec.ts",
        )
        self.changed.write_bytes(b"docs/scrum/week7.md\0" + b"\0".join(path.encode() for path in misplaced) + b"\0")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        for path in (*misplaced, "backend/tests/", "frontend/tests/"):
            with self.subTest(path=path):
                self.assertIn(path, result.stderr)

    def test_source_changes_without_matching_tests_warn(self):
        for path, layer, test_id in (
            (b"frontend/src/App.tsx\0", "frontend", EXISTING),
            (b"backend/app/main.py\0", "backend", FRONTEND),
        ):
            with self.subTest(layer=layer):
                self.register([test_id])
                self.changed.write_bytes(path)
                result = self.check()
                self.assertEqual(result.returncode, 0, result.stderr)
                warning = next((line for line in result.stdout.splitlines() if line.startswith("::warning::")), "")
                self.assertIn(f"no registered {layer} required tests", warning)


class FrontendRunnerTests(unittest.TestCase):
    def report(self, *assertions):
        return {"testResults": [{
            "name": str(self.root / "frontend/tests/sample.test.ts"),
            "assertionResults": [
                {"ancestorTitles": ancestors, "title": title, "status": status}
                for ancestors, title, status in assertions
            ],
        }]}

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_vitest_report_builds_ids_for_passing_tests(self):
        report = self.report(
            (["Sample"], "passes", "passed"),
            (["Sample", "Nested"], "passes too", "passed"),
            (["Sample"], "skips", "skipped"),
            (["Sample"], "not implemented", "todo"),
        )
        self.assertEqual(frontend_runner.passed_test_ids(report, self.root), [
            "frontend/tests/sample.test.ts > Sample > Nested > passes too",
            FRONTEND,
        ])

    def test_failed_vitest_assertion_rejects_report(self):
        report = self.report(
            (["Sample"], "passes", "passed"),
            (["Sample"], "regresses", "failed"),
        )
        with self.assertRaisesRegex(ValueError, "Test did not pass: .*regresses"):
            frontend_runner.passed_test_ids(report, self.root)
