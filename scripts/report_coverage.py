"""Print coverage percentages and add them to the GitHub job summary.

Usage: python scripts/report_coverage.py backend|frontend
The report only lists results; it has no minimum coverage requirement.
"""

import json
import os
from pathlib import Path
import sys


REPORTS = {
    "backend": Path("htmlcov/coverage.json"),
    "frontend": Path("frontend/coverage/coverage-summary.json"),
}


def coverage_rows(layer, report):
    if layer == "backend":
        totals = report["totals"]
        return [
            ("Statements", totals["percent_statements_covered"], totals["covered_lines"], totals["num_statements"]),
            ("Branches", totals["percent_branches_covered"], totals["covered_branches"], totals["num_branches"]),
        ]
    total = report["total"]
    return [
        (name, total[key]["pct"], total[key]["covered"], total[key]["total"])
        for name, key in (
            ("Statements", "statements"),
            ("Branches", "branches"),
            ("Functions", "functions"),
            ("Lines", "lines"),
        )
    ]


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in REPORTS:
        raise SystemExit("Usage: python scripts/report_coverage.py backend|frontend")
    layer = sys.argv[1]
    rows = coverage_rows(layer, json.loads(REPORTS[layer].read_text(encoding="utf-8")))
    text = "\n".join([
        f"### {layer.capitalize()} coverage",
        "",
        "| Metric | Coverage | Covered / Total |",
        "|---|---|---|",
        *(f"| {name} | {percent:.2f}% | {covered} / {total} |" for name, percent, covered, total in rows),
        "",
    ])
    print(text)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            print(text, file=stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
