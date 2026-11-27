"""Validate the repository bank or an import batch without writing files."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

BACKEND = Path(__file__).resolve().parents[1] / "backend"
CONTENT = BACKEND / "app" / "content"
sys.path.insert(0, str(BACKEND))

from app.catalog import project_catalog  # noqa: E402
from app.models import QuestionInput  # noqa: E402

REQUIRED = ("id", "dimension", "topicId", "topic", "type", "difficulty", "stem",
            "options", "correct", "explanation", "sources", "version", "status")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_questions(path):
    rows = read_json(path)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: expected a nonempty JSON array")
    return rows


def normalize_stem(text):
    # Keep case, interior whitespace, and symbols significant for code questions.
    return text.strip().rstrip("。？！?!").rstrip()


def validate_questions(questions, ability_tree, existing=()):
    project_catalog(ability_tree)
    topics = {
        (dimension["id"], topic["id"]): topic["name"]
        for dimension in ability_tree["dimensions"]
        for topic in dimension["topics"]
    }
    errors = []
    ids = {}
    stems = {}
    for row in existing:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("stem"), str):
            raise ValueError("Existing questions require string id and stem fields")
        ids[row["id"]] = f"existing:{row['id']}"
        stems[normalize_stem(row["stem"])] = f"existing:{row['id']}"

    for index, row in enumerate(questions, start=1):
        if not isinstance(row, dict):
            errors.append({"row": index, "field": "", "code": "invalid_record", "message": "Expected an object"})
            continue
        question_id = row.get("id")

        def report(field, code, message, *, row_number=index, identifier=question_id):
            errors.append({"row": row_number, "id": identifier, "field": field, "code": code, "message": message})

        missing = [field for field in REQUIRED if field not in row or row[field] is None]
        for field in missing:
            report(field, "missing_field", "Required by the import contract")
        try:
            QuestionInput.model_validate(row)
        except ValidationError as exc:
            for issue in exc.errors(include_url=False):
                field = ".".join(str(part) for part in issue["loc"])
                if issue["type"] != "missing" or field not in missing:
                    report(field, "invalid_value", issue["msg"])

        if "version" not in missing and (type(row["version"]) is not int or row["version"] < 1):
            report("version", "invalid_value", "Expected an explicit positive integer")
        dimension, topic_id = row.get("dimension"), row.get("topicId")
        if isinstance(dimension, str) and isinstance(topic_id, str):
            if topics.get((dimension, topic_id)) != row.get("topic") or (dimension, topic_id) not in topics:
                report("topicId", "invalid_topic", "Topic must exist in this dimension with the matching display name")
        options = row.get("options")
        if isinstance(options, list) and all(isinstance(o, dict) for o in options):
            option_ids = [o.get("id") for o in options]
            if len(option_ids) != 4 or not all(isinstance(value, str) for value in option_ids) or set(option_ids) != set("ABCD"):
                report("options", "invalid_options", "Expected exactly one each of A, B, C and D")
            option_texts = [o.get("text") for o in options]
            if all(isinstance(text, str) for text in option_texts):
                normalized = {text.strip() for text in option_texts}
                if "" in normalized or len(normalized) != len(option_texts):
                    report("options", "invalid_options", "Options must have nonempty, distinct text")
        correct = row.get("correct")
        kind = row.get("type")
        if isinstance(correct, list):
            allowed_sizes = (1,) if kind == "single" else (2, 3)
            if not all(isinstance(value, str) and value in "ABCD" and len(value) == 1 for value in correct) or (
                len(correct) not in allowed_sizes or len(set(correct)) != len(correct)
            ):
                report("correct", "invalid_answer", "Select one answer for single-choice or two to three distinct answers for multiple-choice")

        if isinstance(question_id, str):
            if question_id in ids:
                report("id", "duplicate_id", f"Duplicates {ids[question_id]}")
            else:
                ids[question_id] = f"row {index} ({question_id})"
        if isinstance(stem := row.get("stem"), str) and (key := normalize_stem(stem)):
            if key in stems:
                report("stem", "duplicate_stem", f"Duplicates {stems[key]}")
            else:
                stems[key] = f"row {index} ({question_id})"
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", nargs="?", type=Path, default=CONTENT / "questions.json")
    parser.add_argument("--ability-tree", type=Path, default=CONTENT / "ability-tree.json")
    parser.add_argument("--existing", type=Path, help="Existing bank to check for duplicate IDs and stems")
    args = parser.parse_args()
    count = 0
    try:
        questions = read_questions(args.questions)
        count = len(questions)
        existing = read_questions(args.existing) if args.existing else ()
        errors = validate_questions(questions, read_json(args.ability_tree), existing)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors = [{"code": "invalid_input", "message": str(exc)}]
    print(json.dumps({"questions": count, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
