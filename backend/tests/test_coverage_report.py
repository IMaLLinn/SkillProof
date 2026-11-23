"""Unit tests for layered coverage reporting, thresholds, anti-regression, and diff warnings."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "report_coverage.py"


def backend_report(
    stmts_covered=930,
    stmts_total=1000,
    branches_covered=820,
    branches_total=1000,
    files=None,
):
    return {
        "totals": {
            "covered_lines": stmts_covered,
            "num_statements": stmts_total,
            "percent_statements_covered": (stmts_covered / stmts_total * 100.0) if stmts_total else 0.0,
            "covered_branches": branches_covered,
            "num_branches": branches_total,
            "percent_branches_covered": (branches_covered / branches_total * 100.0) if branches_total else 0.0,
        },
        "files": files or {},
    }


def _cov_stat(covered, total):
    pct = round((covered / total * 100.0), 2) if total else 100.0
    return {"total": total, "covered": covered, "skipped": 0, "pct": pct}


def frontend_summary(
    *,
    logic_stmts=(90, 100),
    logic_branches=(90, 100),
    ui_stmts=(10, 100),
    ui_branches=(10, 100),
    root="/repo",
    extra_files=None,
):
    files = {
        f"{root}/frontend/src/lib/reportUtils.ts": {
            "statements": _cov_stat(logic_stmts[0] // 2, logic_stmts[1] // 2),
            "branches": _cov_stat(logic_branches[0] // 2, logic_branches[1] // 2),
            "functions": _cov_stat(1, 1),
            "lines": _cov_stat(logic_stmts[0] // 2, logic_stmts[1] // 2),
        },
        f"{root}/frontend/src/api.ts": {
            "statements": _cov_stat(logic_stmts[0] - logic_stmts[0] // 2, logic_stmts[1] - logic_stmts[1] // 2),
            "branches": _cov_stat(logic_branches[0] - logic_branches[0] // 2, logic_branches[1] - logic_branches[1] // 2),
            "functions": _cov_stat(1, 1),
            "lines": _cov_stat(logic_stmts[0] - logic_stmts[0] // 2, logic_stmts[1] - logic_stmts[1] // 2),
        },
        f"{root}/frontend/src/pages/reports/ResultPage.tsx": {
            "statements": _cov_stat(*ui_stmts),
            "branches": _cov_stat(*ui_branches),
            "functions": _cov_stat(0, 1),
            "lines": _cov_stat(*ui_stmts),
        },
        f"{root}/frontend/src/types/report.ts": {
            "statements": _cov_stat(0, 0),
            "branches": _cov_stat(0, 0),
            "functions": _cov_stat(0, 0),
            "lines": _cov_stat(0, 0),
        },
    }
    if extra_files:
        files.update(extra_files)
    total_stmts_cov = sum(entry["statements"]["covered"] for entry in files.values())
    total_stmts = sum(entry["statements"]["total"] for entry in files.values())
    total_br_cov = sum(entry["branches"]["covered"] for entry in files.values())
    total_br = sum(entry["branches"]["total"] for entry in files.values())
    return {
        "total": {
            "statements": _cov_stat(total_stmts_cov, total_stmts),
            "branches": _cov_stat(total_br_cov, total_br),
            "functions": _cov_stat(2, 3),
            "lines": _cov_stat(total_stmts_cov, total_stmts),
        },
        **files,
    }


class CoverageGateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.summary_file = self.root / "summary.md"
        self.env = {
            **os.environ,
            "GITHUB_STEP_SUMMARY": str(self.summary_file),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def write_json(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def run_reporter(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd or self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_backend_passes_at_floor_and_exact_regression_tolerance(self):
        baseline = self.write_json("main.json", backend_report(stmts_covered=906, branches_covered=805))
        current = self.write_json("pr.json", backend_report(stmts_covered=901, branches_covered=800))

        result = self.run_reporter("backend", "--report", str(current), "--baseline", str(baseline), "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("| Backend (`backend/app/`) | Statements | 90.10% |", result.stdout)
        self.assertIn("| PASS |", result.stdout)
        self.assertIn("Backend coverage", self.summary_file.read_text(encoding="utf-8"))

    def test_backend_fails_below_floor_and_writes_summary(self):
        report = self.write_json("pr.json", backend_report(stmts_covered=899, branches_covered=799))

        result = self.run_reporter("backend", "--report", str(report), "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("below floor 90.00%", result.stderr)
        self.assertIn("below floor 80.00%", result.stderr)
        summary = self.summary_file.read_text(encoding="utf-8")
        self.assertIn("FAIL", summary)
        self.assertIn("Blocking gate failures", summary)

    def test_backend_fails_when_drop_exceeds_tolerance_even_above_floor(self):
        baseline = self.write_json("main.json", backend_report(stmts_covered=932, branches_covered=825))
        current = self.write_json("pr.json", backend_report(stmts_covered=926, branches_covered=819))

        result = self.run_reporter("backend", "--report", str(current), "--baseline", str(baseline), "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("dropped 0.60pp below main 93.20%", result.stderr)
        self.assertIn("dropped 0.60pp below main 82.50%", result.stderr)

    def test_frontend_gates_logic_layer_only_and_ignores_ui_drop(self):
        baseline = self.write_json(
            "main-fe.json",
            frontend_summary(
                logic_stmts=(90, 100),
                logic_branches=(92, 100),
                ui_stmts=(60, 100),
                ui_branches=(55, 100),
            ),
        )
        current = self.write_json(
            "pr-fe.json",
            frontend_summary(
                logic_stmts=(90, 100),
                logic_branches=(92, 100),
                ui_stmts=(5, 100),
                ui_branches=(4, 100),
                root=r"C:\work\SkillProof",
            ),
        )

        result = self.run_reporter("frontend", "--report", str(current), "--baseline", str(baseline), "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Logic (`lib/*`, `api.ts`, `authValidation.ts`)", result.stdout)
        self.assertIn("| Pages & Components | Statements | 5.00% |", result.stdout)
        self.assertIn("| Reference |", result.stdout)
        self.assertNotIn("Other (`frontend/src/*`)", result.stdout)

    def test_frontend_fails_when_logic_layer_drops_below_floor_or_baseline(self):
        baseline = self.write_json(
            "main-fe.json",
            frontend_summary(logic_stmts=(90, 100), logic_branches=(88, 100)),
        )
        current = self.write_json(
            "pr-fe.json",
            frontend_summary(logic_stmts=(84, 100), logic_branches=(87, 100)),
        )

        result = self.run_reporter("frontend", "--report", str(current), "--baseline", str(baseline), "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("below floor 85.00%", result.stderr)
        self.assertIn("dropped 6.00pp below main 90.00%", result.stderr)
        self.assertIn("dropped 1.00pp below main 88.00%", result.stderr)

    def test_backend_diff_warns_below_80_without_blocking(self):
        report = self.write_json(
            "pr.json",
            backend_report(
                files={
                    "backend/app/service.py": {
                        "executed_lines": [10, 11],
                        "missing_lines": [12, 13, 14],
                    }
                }
            ),
        )
        diff = self.root / "changes.diff"
        diff.write_text(
            "\n".join([
                "diff --git a/backend/app/service.py b/backend/app/service.py",
                "--- a/backend/app/service.py",
                "+++ b/backend/app/service.py",
                "@@ -9,0 +10,5 @@",
                "+a = 1",
                "+b = 2",
                "+c = 3",
                "+d = 4",
                "+e = 5",
                "diff --git a/backend/app/removed.py b/backend/app/removed.py",
                "--- a/backend/app/removed.py",
                "+++ /dev/null",
                "@@ -1,3 +0,0 @@",
                "-x = 1",
                "diff --git a/scripts/tool.py b/scripts/tool.py",
                "+++ b/scripts/tool.py",
                "@@ -1,0 +2 @@",
                "+print('ignored')",
            ]),
            encoding="utf-8",
        )

        result = self.run_reporter("backend", "--report", str(report), "--diff-file", str(diff), "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("::warning::Changed backend statement coverage is 40.00% (2/5)", result.stdout)
        self.assertIn("WARN (non-blocking)", result.stdout)
        self.assertIn("`backend/app/service.py`", result.stdout)

    def test_frontend_diff_measures_logic_layer_and_ignores_pages(self):
        summary = self.write_json("fe/coverage-summary.json", frontend_summary())
        self.write_json(
            "fe/coverage-final.json",
            {
                "/repo/frontend/src/lib/reportUtils.ts": {
                    "statementMap": {
                        "0": {"start": {"line": 4}, "end": {"line": 8}},
                        "1": {"start": {"line": 12}, "end": {"line": 12}},
                        "2": {"start": {"line": 15}, "end": {"line": 15}},
                    },
                    "s": {"0": 2, "1": 0, "2": 0},
                },
                "/repo/frontend/src/pages/reports/ResultPage.tsx": {
                    "statementMap": {
                        "0": {"start": {"line": 10}, "end": {"line": 10}},
                    },
                    "s": {"0": 0},
                },
            },
        )
        diff = self.root / "fe.diff"
        diff.write_text(
            "\n".join([
                "+++ b/frontend/src/lib/reportUtils.ts",
                "@@ -6,0 +6 @@",
                "+  'algorithms',",
                "@@ -12,0 +12,4 @@",
                "+const x = 1",
                "+// comment",
                "+// comment",
                "+const y = 2",
                "+++ b/frontend/src/pages/reports/ResultPage.tsx",
                "@@ -10,0 +10 @@",
                "+return <div />",
            ]),
            encoding="utf-8",
        )

        result = self.run_reporter("frontend", "--report", str(summary), "--diff-file", str(diff), "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("::warning::Changed frontend logic statement coverage is 33.33% (1/3)", result.stdout)
        self.assertIn("`frontend/src/lib/reportUtils.ts`", result.stdout)
        self.assertNotIn("ResultPage.tsx`", result.stdout)

    def test_frontend_diff_requires_detail_report(self):
        summary = self.write_json("fe/coverage-summary.json", frontend_summary())
        diff = self.root / "empty.diff"
        diff.write_text("", encoding="utf-8")

        result = self.run_reporter("frontend", "--report", str(summary), "--diff-file", str(diff), "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("coverage-final.json", result.stderr)

    def test_diff_base_reads_real_git_diff_and_passes_when_covered(self):
        repo = self.root / "gitrepo"
        repo.mkdir()
        def git(*args):
            return subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, text=True
            )
        git("init", "-q")
        git("config", "user.name", "Tester")
        git("config", "user.email", "tester@example.com")
        target = repo / "backend" / "app" / "calc.py"
        target.parent.mkdir(parents=True)
        target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "base")
        target.write_text("def add(a, b):\n    total = a + b\n    return total\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "change")

        report = self.write_json(
            "git-backend.json",
            backend_report(
                files={
                    "backend/app/calc.py": {
                        "executed_lines": [1, 2, 3],
                        "missing_lines": [],
                    }
                }
            ),
        )
        result = self.run_reporter(
            "backend", "--report", str(report), "--diff-base", "HEAD~1", "--check", cwd=repo
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("100.00% (2 / 2)", result.stdout)
        self.assertNotIn("::warning::", result.stdout)


if __name__ == "__main__":
    unittest.main()
