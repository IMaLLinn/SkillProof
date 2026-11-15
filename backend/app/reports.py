"""Read persisted reports without recomputing against the current question bank."""

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .catalog import DIMENSION_IDS
from .security import Principal, get_db, require_user

router = APIRouter(prefix="/api", tags=["reports"])


def parse_report_snapshot(value: str, attempt_id: str) -> dict:
    report = json.loads(value)
    if not isinstance(report, dict) or report.get("id") != attempt_id:
        raise ValueError("Invalid report snapshot")
    return report


def report_score_summary(report: dict) -> tuple[int | float, list[dict]]:
    score = report.get("score")
    dimensions = report.get("dimensions")
    if type(score) not in (int, float) or not 0 <= score <= 100 or not isinstance(dimensions, list):
        raise ValueError("Invalid history scores")
    by_id = {}
    for dimension in dimensions:
        if not isinstance(dimension, dict) or dimension.get("id") not in DIMENSION_IDS:
            raise ValueError("Invalid report dimension")
        dimension_id = dimension["id"]
        name, value = dimension.get("name"), dimension.get("score")
        correct, total = dimension.get("correct"), dimension.get("total")
        if (
            dimension_id in by_id or not isinstance(name, str) or not name.strip()
            or type(value) not in (int, float) or not 0 <= value <= 100
            or type(correct) is not int or type(total) is not int or not 0 <= correct <= total or total == 0
        ):
            raise ValueError("Invalid report dimension")
        by_id[dimension_id] = {
            "id": dimension_id, "name": name, "score": value, "correct": correct, "total": total,
        }
    if len(by_id) != len(DIMENSION_IDS):
        raise ValueError("Incomplete report dimensions")
    return score, [by_id[dimension_id] for dimension_id in DIMENSION_IDS]


def read_report(connection: sqlite3.Connection, attempt_id: str, user_id: str) -> dict:
    row = connection.execute(
        "SELECT status, report_json FROM attempts WHERE id=? AND user_id=?",
        (attempt_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "测评不存在")
    if row[0] != "submitted":
        raise HTTPException(409, "测评提交后才会生成报告")
    try:
        report = parse_report_snapshot(row[1], attempt_id)
        report_score_summary(report)
        return report
    except (ValueError, TypeError) as exc:
        raise HTTPException(500, "结果快照无效") from exc


@router.get("/reports/{attempt_id}")
def get_report(
    attempt_id: str,
    principal: Principal = Depends(require_user),
    connection=Depends(get_db),
) -> dict:
    return read_report(connection, attempt_id, principal.user["id"])
