"""Report coverage, enforce layered gates and anti-regression, and warn on low diff coverage.

Usage:
    python scripts/report_coverage.py backend|frontend [options]

Blocking gates (enabled with --check):
- Backend (backend/app/): Statements >= 90%, Branches >= 80%, and no drop > 0.5pp vs baseline.
- Frontend logic layer (frontend/src/lib/*, api.ts, authValidation.ts):
  Statements >= 85%, Branches >= 80%, and no drop > 0.5pp vs baseline.

Non-blocking reporting:
- Frontend pages/components and overall totals are reported for reference only.
- Changed-statement coverage (backend/app/ or frontend logic layer) emits a ::warning::
  below 80% when --diff-base or --diff-file is provided, without failing CI.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys


REPORTS = {
    "backend": Path("htmlcov/coverage.json"),
    "frontend": Path("frontend/coverage/coverage-summary.json"),
}

BACKEND_FLOORS = {
    "Statements": 90.0,
    "Branches": 80.0,
}

FRONTEND_LOGIC_FLOORS = {
    "Statements": 85.0,
    "Branches": 80.0,
}

REGRESSION_TOLERANCE = 0.5
DIFF_RECOMMENDED = 80.0
EPSILON = 1e-9

FRONTEND_LOGIC_FILES = frozenset({
    "frontend/src/api.ts",
    "frontend/src/authValidation.ts",
})
FRONTEND_LOGIC_PREFIX = "frontend/src/lib/"
FRONTEND_UI_FILES = frozenset({
    "frontend/src/App.tsx",
    "frontend/src/main.tsx",
})
FRONTEND_UI_PREFIXES = (
    "frontend/src/pages/",
    "frontend/src/components/",
)

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class CoverageMetric:
    scope: str
    name: str
    pct: float
    covered: int
    total: int
    floor: float | None = None
    gated: bool = False


@dataclass(frozen=True)
class DiffFileCoverage:
    path: str
    covered: int
    total: int

    @property
    def pct(self) -> float:
        return (self.covered / self.total * 100.0) if self.total else 100.0


@dataclass(frozen=True)
class DiffCoverageResult:
    covered: int
    total: int
    files: tuple[DiffFileCoverage, ...]

    @property
    def pct(self) -> float | None:
        return (self.covered / self.total * 100.0) if self.total else None


def normalize_path(raw: str, anchor: str | None = None) -> str:
    path = raw.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if anchor:
        if path.startswith(anchor):
            return path
        marker = f"/{anchor}"
        index = path.rfind(marker)
        if index != -1:
            return path[index + 1:]
        raise ValueError(f"Path {raw!r} is outside expected root {anchor!r}")
    return path


def classify_frontend_file(repo_path: str) -> str:
    if repo_path in FRONTEND_LOGIC_FILES or repo_path.startswith(FRONTEND_LOGIC_PREFIX):
        return "logic"
    if repo_path in FRONTEND_UI_FILES or repo_path.startswith(FRONTEND_UI_PREFIXES):
        return "ui"
    return "other"


def _percent(covered: int, total: int) -> float:
    return (covered / total * 100.0) if total > 0 else 100.0


def extract_backend_metrics(report: dict) -> list[CoverageMetric]:
    totals = report["totals"]
    num_statements = int(totals["num_statements"])
    num_branches = int(totals["num_branches"])
    if num_statements <= 0 or num_branches <= 0:
        raise ValueError("Backend coverage report must contain executable statements and branches")
    return [
        CoverageMetric(
            scope="Backend (`backend/app/`)",
            name="Statements",
            pct=float(totals["percent_statements_covered"]),
            covered=int(totals["covered_lines"]),
            total=num_statements,
            floor=BACKEND_FLOORS["Statements"],
            gated=True,
        ),
        CoverageMetric(
            scope="Backend (`backend/app/`)",
            name="Branches",
            pct=float(totals["percent_branches_covered"]),
            covered=int(totals["covered_branches"]),
            total=num_branches,
            floor=BACKEND_FLOORS["Branches"],
            gated=True,
        ),
    ]


def extract_frontend_metrics(report: dict) -> list[CoverageMetric]:
    buckets = {
        "logic": {"statements": [0, 0], "branches": [0, 0]},
        "ui": {"statements": [0, 0], "branches": [0, 0]},
        "other": {"statements": [0, 0], "branches": [0, 0]},
    }
    for key, entry in report.items():
        if key == "total":
            continue
        repo_path = normalize_path(key, "frontend/src/")
        layer = classify_frontend_file(repo_path)
        for metric_key in ("statements", "branches"):
            buckets[layer][metric_key][0] += int(entry[metric_key]["covered"])
            buckets[layer][metric_key][1] += int(entry[metric_key]["total"])

    logic_stmts = buckets["logic"]["statements"]
    logic_branches = buckets["logic"]["branches"]
    if logic_stmts[1] <= 0 or logic_branches[1] <= 0:
        raise ValueError("Frontend coverage report must contain logic-layer statements and branches")

    metrics: list[CoverageMetric] = [
        CoverageMetric(
            scope="Logic (`lib/*`, `api.ts`, `authValidation.ts`)",
            name="Statements",
            pct=_percent(logic_stmts[0], logic_stmts[1]),
            covered=logic_stmts[0],
            total=logic_stmts[1],
            floor=FRONTEND_LOGIC_FLOORS["Statements"],
            gated=True,
        ),
        CoverageMetric(
            scope="Logic (`lib/*`, `api.ts`, `authValidation.ts`)",
            name="Branches",
            pct=_percent(logic_branches[0], logic_branches[1]),
            covered=logic_branches[0],
            total=logic_branches[1],
            floor=FRONTEND_LOGIC_FLOORS["Branches"],
            gated=True,
        ),
        CoverageMetric(
            scope="Pages & Components",
            name="Statements",
            pct=_percent(*buckets["ui"]["statements"]),
            covered=buckets["ui"]["statements"][0],
            total=buckets["ui"]["statements"][1],
        ),
        CoverageMetric(
            scope="Pages & Components",
            name="Branches",
            pct=_percent(*buckets["ui"]["branches"]),
            covered=buckets["ui"]["branches"][0],
            total=buckets["ui"]["branches"][1],
        ),
    ]

    if buckets["other"]["statements"][1] > 0 or buckets["other"]["branches"][1] > 0:
        metrics.extend([
            CoverageMetric(
                scope="Other (`frontend/src/*`)",
                name="Statements",
                pct=_percent(*buckets["other"]["statements"]),
                covered=buckets["other"]["statements"][0],
                total=buckets["other"]["statements"][1],
            ),
            CoverageMetric(
                scope="Other (`frontend/src/*`)",
                name="Branches",
                pct=_percent(*buckets["other"]["branches"]),
                covered=buckets["other"]["branches"][0],
                total=buckets["other"]["branches"][1],
            ),
        ])

    total = report["total"]
    for name, key in (
        ("Statements", "statements"),
        ("Branches", "branches"),
        ("Functions", "functions"),
        ("Lines", "lines"),
    ):
        metrics.append(
            CoverageMetric(
                scope="Overall (`frontend/src/`)",
                name=name,
                pct=float(total[key]["pct"]),
                covered=int(total[key]["covered"]),
                total=int(total[key]["total"]),
            )
        )
    return metrics


def extract_metrics(layer: str, report: dict) -> list[CoverageMetric]:
    if layer == "backend":
        return extract_backend_metrics(report)
    if layer == "frontend":
        return extract_frontend_metrics(report)
    raise ValueError(f"Unsupported layer: {layer!r}")


def evaluate_gates(
    metrics: list[CoverageMetric],
    baseline_metrics: list[CoverageMetric] | None = None,
) -> tuple[list[tuple[CoverageMetric, CoverageMetric | None, str]], list[str]]:
    baseline_map = (
        {(m.scope, m.name): m for m in baseline_metrics}
        if baseline_metrics is not None
        else {}
    )
    rows: list[tuple[CoverageMetric, CoverageMetric | None, str]] = []
    failures: list[str] = []

    for metric in metrics:
        base = baseline_map.get((metric.scope, metric.name))
        if not metric.gated:
            rows.append((metric, base, "Reference"))
            continue

        metric_failures: list[str] = []
        if metric.floor is not None and metric.pct + EPSILON < metric.floor:
            metric_failures.append(
                f"{metric.scope} {metric.name} {metric.pct:.2f}% is below floor {metric.floor:.2f}%"
            )
        if base is not None and metric.pct + REGRESSION_TOLERANCE + EPSILON < base.pct:
            drop = base.pct - metric.pct
            metric_failures.append(
                f"{metric.scope} {metric.name} {metric.pct:.2f}% dropped {drop:.2f}pp "
                f"below main {base.pct:.2f}% (allowed drop: {REGRESSION_TOLERANCE:.2f}pp)"
            )

        if metric_failures:
            failures.extend(metric_failures)
            rows.append((metric, base, "FAIL"))
        else:
            rows.append((metric, base, "PASS"))

    return rows, failures


def parse_unified_diff(diff_text: str) -> dict[str, set[int]]:
    changed: dict[str, set[int]] = {}
    current_path: str | None = None
    line_no: int | None = None

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ "):
            target = raw_line[4:].split("\t", 1)[0].strip()
            if target == "/dev/null":
                current_path = None
            else:
                if target.startswith("b/"):
                    target = target[2:]
                current_path = normalize_path(target)
            line_no = None
            continue
        if raw_line.startswith("--- ") or raw_line.startswith("diff --git "):
            line_no = None
            continue
        match = HUNK_HEADER.match(raw_line)
        if match:
            if current_path is None:
                line_no = None
                continue
            new_start = int(match.group(1))
            new_count = int(match.group(2)) if match.group(2) is not None else 1
            line_no = new_start if new_count > 0 else None
            continue
        if current_path is None or line_no is None:
            continue
        if raw_line.startswith("+"):
            changed.setdefault(current_path, set()).add(line_no)
            line_no += 1
        elif raw_line.startswith(" "):
            line_no += 1

    return changed


def git_diff_text(diff_base: str, layer: str) -> str:
    scope = ["backend/app"] if layer == "backend" else ["frontend/src"]
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "diff",
            "--unified=0",
            "--no-color",
            "--no-ext-diff",
            diff_base,
            "HEAD",
            "--",
            *scope,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git diff {diff_base}..HEAD failed: {result.stderr.strip()}")
    return result.stdout


def evaluate_backend_diff(report: dict, changed_lines: dict[str, set[int]]) -> DiffCoverageResult:
    files_by_path: dict[str, dict] = {}
    for raw_path, file_data in report.get("files", {}).items():
        norm = normalize_path(raw_path)
        marker = "/backend/app/"
        if not norm.startswith("backend/app/") and marker in norm:
            norm = norm[norm.rfind(marker) + 1:]
        files_by_path[norm] = file_data

    file_results: list[DiffFileCoverage] = []
    total_covered = 0
    total_stmts = 0

    for path in sorted(changed_lines):
        if not (path.startswith("backend/app/") and path.endswith(".py")):
            continue
        file_data = files_by_path.get(path)
        if not file_data:
            continue
        lines = changed_lines[path]
        executed = set(file_data.get("executed_lines", ()))
        missing = set(file_data.get("missing_lines", ()))
        covered = len(lines & executed)
        uncovered = len(lines & missing)
        total = covered + uncovered
        if total > 0:
            file_results.append(DiffFileCoverage(path=path, covered=covered, total=total))
            total_covered += covered
            total_stmts += total

    return DiffCoverageResult(covered=total_covered, total=total_stmts, files=tuple(file_results))


def evaluate_frontend_diff(detail_report: dict, changed_lines: dict[str, set[int]]) -> DiffCoverageResult:
    files_by_path: dict[str, dict] = {}
    for raw_path, file_data in detail_report.items():
        norm = normalize_path(raw_path, "frontend/src/")
        files_by_path[norm] = file_data

    file_results: list[DiffFileCoverage] = []
    total_covered = 0
    total_stmts = 0

    for path in sorted(changed_lines):
        if classify_frontend_file(path) != "logic":
            continue
        file_data = files_by_path.get(path)
        if not file_data:
            continue
        lines = changed_lines[path]
        statement_map = file_data.get("statementMap", {})
        counts = file_data.get("s", {})
        covered = 0
        total = 0
        for stmt_id, loc in statement_map.items():
            start = int(loc["start"]["line"])
            end_info = loc.get("end") or {}
            end = int(end_info["line"]) if end_info.get("line") is not None else start
            if any(start <= line <= end for line in lines):
                total += 1
                if int(counts.get(stmt_id, 0)) > 0:
                    covered += 1
        if total > 0:
            file_results.append(DiffFileCoverage(path=path, covered=covered, total=total))
            total_covered += covered
            total_stmts += total

    return DiffCoverageResult(covered=total_covered, total=total_stmts, files=tuple(file_results))


def format_markdown(
    layer: str,
    rows: list[tuple[CoverageMetric, CoverageMetric | None, str]],
    has_baseline: bool,
    diff_result: DiffCoverageResult | None,
    failures: list[str],
) -> str:
    lines = [f"### {layer.capitalize()} coverage", ""]
    if has_baseline:
        lines.append("| Scope | Metric | Coverage | Covered / Total | Main | Delta | Rule | Status |")
        lines.append("|---|---|---|---|---|---|---|---|")
    else:
        lines.append("| Scope | Metric | Coverage | Covered / Total | Rule | Status |")
        lines.append("|---|---|---|---|---|---|")

    for metric, base, status in rows:
        if metric.gated and metric.floor is not None:
            rule = f">= {metric.floor:.0f}%"
            if has_baseline:
                rule += f", main -{REGRESSION_TOLERANCE:.1f}pp"
        else:
            rule = "—"

        if has_baseline:
            if base is not None:
                delta = metric.pct - base.pct
                main_cell = f"{base.pct:.2f}%"
                delta_cell = f"{delta:+.2f}pp"
            else:
                main_cell = "—"
                delta_cell = "—"
            lines.append(
                f"| {metric.scope} | {metric.name} | {metric.pct:.2f}% | "
                f"{metric.covered} / {metric.total} | {main_cell} | {delta_cell} | {rule} | {status} |"
            )
        else:
            lines.append(
                f"| {metric.scope} | {metric.name} | {metric.pct:.2f}% | "
                f"{metric.covered} / {metric.total} | {rule} | {status} |"
            )

    if diff_result is not None:
        scope_desc = "backend (`backend/app/`)" if layer == "backend" else "frontend logic (`lib/*`, `api.ts`, `authValidation.ts`)"
        lines.append("")
        if diff_result.total == 0:
            lines.append(f"**Changed-code statement coverage ({scope_desc})**: N/A (no executable statements changed in scope)")
        else:
            diff_pct = diff_result.pct
            assert diff_pct is not None
            diff_status = "PASS" if diff_pct + EPSILON >= DIFF_RECOMMENDED else "WARN (non-blocking)"
            lines.append(
                f"**Changed-code statement coverage ({scope_desc})**: "
                f"{diff_pct:.2f}% ({diff_result.covered} / {diff_result.total}) — "
                f"recommended >= {DIFF_RECOMMENDED:.0f}% — **{diff_status}**"
            )
            if diff_result.files:
                lines.extend([
                    "",
                    "| Changed file | Statement coverage | Covered / Total |",
                    "|---|---|---|",
                    *(
                        f"| `{item.path}` | {item.pct:.2f}% | {item.covered} / {item.total} |"
                        for item in diff_result.files
                    ),
                ])

    if failures:
        lines.extend(["", "**Blocking gate failures:**", *(f"- {reason}" for reason in failures)])

    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report coverage metrics, check gates against floors/baseline, and warn on diff coverage."
    )
    parser.add_argument("layer", choices=sorted(REPORTS), help="Coverage layer to report")
    parser.add_argument("--report", type=Path, help="Path to coverage JSON report")
    parser.add_argument("--detail-report", type=Path, help="Path to frontend coverage-final.json for diff coverage")
    parser.add_argument("--baseline", type=Path, help="Path to main-branch baseline coverage JSON")
    diff_group = parser.add_mutually_exclusive_group()
    diff_group.add_argument("--diff-base", help="Git base ref to diff against HEAD for changed-code coverage")
    diff_group.add_argument("--diff-file", type=Path, help="Unified diff file for changed-code coverage")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if any blocking gate fails")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    layer = args.layer
    report_path = args.report or REPORTS[layer]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    metrics = extract_metrics(layer, report)

    baseline_metrics: list[CoverageMetric] | None = None
    if args.baseline is not None:
        baseline_report = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline_metrics = extract_metrics(layer, baseline_report)

    rows, failures = evaluate_gates(metrics, baseline_metrics)

    diff_result: DiffCoverageResult | None = None
    if args.diff_base or args.diff_file is not None:
        diff_text = (
            args.diff_file.read_text(encoding="utf-8")
            if args.diff_file is not None
            else git_diff_text(args.diff_base, layer)
        )
        changed_lines = parse_unified_diff(diff_text)
        if layer == "backend":
            diff_result = evaluate_backend_diff(report, changed_lines)
        else:
            detail_path = args.detail_report or report_path.with_name("coverage-final.json")
            if not detail_path.is_file():
                raise ValueError(f"Frontend diff coverage requires detailed report: {detail_path}")
            detail_report = json.loads(detail_path.read_text(encoding="utf-8"))
            diff_result = evaluate_frontend_diff(detail_report, changed_lines)

    markdown = format_markdown(
        layer=layer,
        rows=rows,
        has_baseline=baseline_metrics is not None,
        diff_result=diff_result,
        failures=failures,
    )
    print(markdown)

    if diff_result is not None and diff_result.total > 0 and diff_result.pct is not None:
        if diff_result.pct + EPSILON < DIFF_RECOMMENDED:
            scope_label = "backend" if layer == "backend" else "frontend logic"
            print(
                f"::warning::Changed {scope_label} statement coverage is "
                f"{diff_result.pct:.2f}% ({diff_result.covered}/{diff_result.total}), "
                f"below the recommended {DIFF_RECOMMENDED:.0f}% (non-blocking)."
            )

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            print(markdown, file=stream)

    if args.check and failures:
        for reason in failures:
            print(f"::error::{reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(f"Coverage report failed: {error}")
