"""Run the frontend suite and publish the IDs of tests that passed."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def passed_test_ids(report, root):
    passed = set()
    for test_file in report["testResults"]:
        path = Path(test_file["name"]).relative_to(root).as_posix()
        for assertion in test_file["assertionResults"]:
            status = assertion["status"]
            if status == "passed":
                passed.add(" > ".join([path, *assertion["ancestorTitles"], assertion["title"]]))
            elif status not in ("skipped", "todo"):
                raise ValueError(f"Test did not pass: {path} > {assertion['title']} ({status})")
    if report.get("success") is False:
        raise ValueError("Vitest reported an unsuccessful run")
    return sorted(passed)


def main():
    root = Path.cwd()
    npx = "npx.cmd" if os.name == "nt" else "npx"
    try:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "vitest.json"
            subprocess.run(
                [npx, "vitest", "run", "--reporter=json", f"--outputFile={report_path}"],
                cwd=root / "frontend",
                check=True,
            )
            passed = passed_test_ids(json.loads(report_path.read_text(encoding="utf-8")), root)
        if not passed:
            raise ValueError("No frontend tests passed")
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError) as error:
        print(f"Frontend test run failed: {error}", file=sys.stderr)
        return 1

    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            print(f"passed_tests={json.dumps(passed)}", file=stream)
    print(f"Frontend tests passed: {len(passed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
