"""Check an Issue's required tests against the results of this CI run."""

import json
import os
import re
import sys
from fnmatch import fnmatchcase
from pathlib import Path

ISSUE_REFERENCE = re.compile(
    r"(?:refs|closes|fixes|resolves)[ \t]+(#[1-9][0-9]*(?:\s*[,，]\s*#[1-9][0-9]*)*)"
    r"(?:[ \t]*[（(].*[）)])?",
    re.IGNORECASE,
)


def issue_numbers(body):
    numbers = set()
    for line in body.splitlines():
        if match := ISSUE_REFERENCE.fullmatch(line.strip()):
            numbers.update(re.findall(r"#([0-9]+)", match[1]))
    return numbers


def test_ids(values, source):
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValueError(f"{source} must contain a non-empty list of test IDs")
    return set(values)


def passed_test_ids(variable, source):
    try:
        values = json.loads(os.environ.get(variable) or "null")
    except json.JSONDecodeError as error:
        raise ValueError(f"{source} must be valid JSON: {error.msg}") from None
    return test_ids(values, source)


def check_test_locations(paths):
    misplaced = []
    for path in paths:
        directory, _, name = path.rpartition("/")
        backend_test = fnmatchcase(name, "test_*.py")
        frontend_test = name.endswith((".test.ts", ".test.tsx"))
        if (directory == "backend/tests" and backend_test) or (
            path.startswith("frontend/tests/") and frontend_test
        ):
            continue
        if backend_test or any(fnmatchcase(name, pattern) for pattern in (
            "*_test.py", "*.test.*", "*.spec.*",
        )):
            misplaced.append(path)
    if misplaced:
        raise ValueError(
            "Place test files in backend/tests/ (test_*.py) or frontend/tests/ (*.test.ts or *.test.tsx): "
            + ", ".join(repr(path) for path in sorted(misplaced))
        )


def main():
    if os.environ.get("FRONTEND_RESULT") != "success" or os.environ.get("BACKEND_RESULT") != "success":
        raise ValueError("Frontend and backend checks must both pass")

    backend_passed = passed_test_ids("PASSED_TESTS", "Backend test results")
    frontend_passed = passed_test_ids("FRONTEND_PASSED_TESTS", "Frontend test results")
    changed = Path(os.environ["CHANGED_FILES"]).read_bytes().split(b"\0")
    paths = [os.fsdecode(path) for path in changed if path]
    check_test_locations(paths)
    if paths and all(path.startswith("docs/scrum/") and path.endswith(".md") for path in paths):
        print("Only Scrum Markdown changed. Required test registration is not needed.")
        return 0

    pr = json.loads(Path(os.environ["PR_DETAILS"]).read_text(encoding="utf-8"))
    issues = issue_numbers(pr.get("body") or "")
    if not issues:
        raise ValueError("Add an Issue reference on its own line in the PR body, e.g. Refs #40")

    required = set()
    for issue in sorted(issues, key=int):
        registration = Path("tests/acceptance/issues") / f"{issue}.json"
        try:
            data = json.loads(registration.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError(f"Issue #{issue} is missing its required test list: {registration}") from None
        ids = data.get("required_tests") if isinstance(data, dict) else None
        required.update(test_ids(ids, f"{registration}: required_tests"))

    missing = required - (backend_passed | frontend_passed)
    if missing:
        raise ValueError("Required tests did not pass: " + ", ".join(sorted(missing)))
    for folder, layer, passed in (
        ("frontend/src/", "frontend", frontend_passed),
        ("backend/app/", "backend", backend_passed),
    ):
        if required.isdisjoint(passed) and any(path.startswith(folder) for path in paths):
            print(f"::warning::Changes in {folder} have no registered {layer} required tests. Review test coverage.")
    print(f"QA checks passed: {len(required)} required tests for Issues " + ", ".join(
        f"#{issue}" for issue in sorted(issues, key=int)
    ))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        sys.exit(f"QA check failed: {error}")
