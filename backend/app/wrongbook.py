"""Owner-scoped wrong answers and independent practice on immutable question copies."""

import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import UUID4, Field, field_validator

from .catalog import DIMENSION_IDS, DIMENSION_NAMES
from .db import dump, now_iso, transaction
from .models import InputModel
from .security import Principal, get_db, require_user

router = APIRouter(prefix="/api/wrong-questions", tags=["wrongbook"])
QUESTION_FIELDS = (
    "id", "dimension", "topicId", "topic", "type", "difficulty", "stem", "options",
    "correct", "explanation", "sources", "version",
)


class PracticeInput(InputModel):
    requestId: UUID4
    selected: list[Literal["A", "B", "C", "D"]] = Field(min_length=1, max_length=4)

    @field_validator("selected")
    @classmethod
    def distinct_options(cls, selected):
        if len(selected) != len(set(selected)):
            raise ValueError("选项不可重复")
        return sorted(selected)


class MasteryInput(InputModel):
    mastered: bool = Field(strict=True)


def collect_wrong_questions(con, attempt, submitted_at: str) -> None:
    """Called inside successful submission's transaction, never during draft saving."""
    state = con.execute(
        "SELECT status FROM attempts WHERE id=? AND user_id=?", (attempt["id"], attempt["user_id"]),
    ).fetchone()
    if state is None or state["status"] != "submitted":
        raise ValueError("Wrong answers may only be collected after submission")
    answers = json.loads(attempt["answers_json"])
    for question in json.loads(attempt["questions_json"]):
        selected = answers.get(question["id"], [])
        if set(selected) == set(question["correct"]):
            continue
        # Use the submitted attempt, not the mutable current question bank.
        snapshot = {key: question[key] for key in QUESTION_FIELDS}
        snapshot["options"] = [{"id": option["id"], "text": option["text"]} for option in question["options"]]
        snapshot["sources"] = [{"title": source["title"], "url": source["url"]} for source in question["sources"]]
        con.execute(
            "INSERT OR IGNORE INTO wrong_questions("
            "id,user_id,attempt_id,role_id,role_name,question_id,dimension,topic_id,topic,"
            "question_json,original_answer_json,collected_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid4()), attempt["user_id"], attempt["id"], attempt["role_id"], attempt["role_name"],
             question["id"], question["dimension"], question["topicId"], question["topic"],
             dump(snapshot), dump(sorted(selected)), submitted_at),
        )


SUMMARY_SELECT = """
SELECT w.*,
 (SELECT COUNT(*) FROM wrong_question_practices p
  WHERE p.wrong_question_id=w.id AND p.user_id=w.user_id) AS practice_count,
 (SELECT is_correct FROM wrong_question_practices p
  WHERE p.wrong_question_id=w.id AND p.user_id=w.user_id
  ORDER BY created_at DESC,id DESC LIMIT 1) AS last_correct,
 (SELECT created_at FROM wrong_question_practices p
  WHERE p.wrong_question_id=w.id AND p.user_id=w.user_id
  ORDER BY created_at DESC,id DESC LIMIT 1) AS last_practiced_at
FROM wrong_questions w
"""


def owned_question(con, question_id: str, user_id: str):
    row = con.execute(SUMMARY_SELECT + " WHERE w.id=? AND w.user_id=?", (question_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "错题不存在")
    return row


def summary_view(row) -> dict:
    question = json.loads(row["question_json"])
    return {
        "id": row["id"], "attemptId": row["attempt_id"], "roleId": row["role_id"],
        "roleName": row["role_name"], "questionId": row["question_id"],
        "dimension": row["dimension"], "dimensionName": DIMENSION_NAMES[row["dimension"]],
        "topicId": row["topic_id"], "topic": row["topic"], "stem": question["stem"],
        "type": question["type"], "questionVersion": question["version"],
        "collectedAt": row["collected_at"], "mastered": bool(row["mastered"]),
        "masteryUpdatedAt": row["mastery_updated_at"], "practiceCount": row["practice_count"],
        "lastPractice": None if row["last_correct"] is None else {
            "isCorrect": bool(row["last_correct"]), "createdAt": row["last_practiced_at"],
        },
    }


def practice_view(row) -> dict:
    return {"id": row["id"], "selected": json.loads(row["selected_json"]),
            "isCorrect": bool(row["is_correct"]), "createdAt": row["created_at"]}


def detail_view(con, row) -> dict:
    return {
        **summary_view(row),
        "question": json.loads(row["question_json"]),
        "originalAnswer": json.loads(row["original_answer_json"]),
        "practices": [practice_view(p) for p in con.execute(
            "SELECT * FROM wrong_question_practices WHERE wrong_question_id=? AND user_id=? "
            "ORDER BY created_at DESC,id DESC", (row["id"], row["user_id"]),
        )],
    }


@router.get("")
def list_wrong_questions(
    roleId: str | None = Query(default=None, max_length=64),
    dimension: str | None = Query(default=None, max_length=64),
    topicId: str | None = Query(default=None, max_length=128),
    status: Literal["review", "mastered", "all"] = "review",
    limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_user), con=Depends(get_db),
):
    if dimension is not None and dimension not in DIMENSION_IDS:
        raise HTTPException(422, "未知能力维度")
    user_id = principal.user["id"]
    clauses, parameters = ["w.user_id=?"], [user_id]
    for column, value in (("role_id", roleId), ("dimension", dimension), ("topic_id", topicId)):
        if value is not None:
            clauses.append(f"w.{column}=?")
            parameters.append(value)
    if status != "all":
        clauses.append("w.mastered=?")
        parameters.append(int(status == "mastered"))
    where = " WHERE " + " AND ".join(clauses)
    # Keep count, rows and filter choices consistent during simultaneous submissions.
    con.execute("BEGIN")
    try:
        total = con.execute("SELECT COUNT(*) FROM wrong_questions w" + where, parameters).fetchone()[0]
        items = [summary_view(row) for row in con.execute(
            SUMMARY_SELECT + where + " ORDER BY w.collected_at DESC,w.id DESC LIMIT ? OFFSET ?",
            [*parameters, limit, offset],
        )]
        counts = con.execute(
            "SELECT COUNT(*),COALESCE(SUM(mastered),0) FROM wrong_questions WHERE user_id=?", (user_id,),
        ).fetchone()
        filters = [{"roleId": row[0], "roleName": row[1], "dimension": row[2],
                    "dimensionName": DIMENSION_NAMES[row[2]], "topicId": row[3], "topic": row[4]}
                   for row in con.execute(
                       "SELECT DISTINCT role_id,role_name,dimension,topic_id,topic FROM wrong_questions "
                       "WHERE user_id=? ORDER BY role_name,dimension,topic_id", (user_id,),
                   )]
        return {"items": items, "total": total, "limit": limit, "offset": offset,
                "counts": {"all": counts[0], "review": counts[0] - counts[1], "mastered": counts[1]},
                "filters": filters}
    finally:
        con.execute("ROLLBACK")


@router.get("/{question_id}")
def get_wrong_question(question_id: str, principal: Principal = Depends(require_user), con=Depends(get_db)):
    return detail_view(con, owned_question(con, question_id, principal.user["id"]))


@router.patch("/{question_id}")
def set_mastery(
    question_id: str, payload: MasteryInput,
    principal: Principal = Depends(require_user), con=Depends(get_db),
):
    with transaction(con):
        row = owned_question(con, question_id, principal.user["id"])
        if bool(row["mastered"]) != payload.mastered:
            con.execute("UPDATE wrong_questions SET mastered=?,mastery_updated_at=? WHERE id=? AND user_id=?",
                        (int(payload.mastered), now_iso(), question_id, principal.user["id"]))
        return detail_view(con, owned_question(con, question_id, principal.user["id"]))


@router.post("/{question_id}/practice")
def practice_wrong_question(
    question_id: str, payload: PracticeInput,
    principal: Principal = Depends(require_user), con=Depends(get_db),
):
    user_id = principal.user["id"]
    with transaction(con):
        row = owned_question(con, question_id, user_id)
        question = json.loads(row["question_json"])
        if question["type"] == "single" and len(payload.selected) != 1:
            raise HTTPException(422, "单选题只能选择一个选项")
        if not set(payload.selected) <= {option["id"] for option in question["options"]}:
            raise HTTPException(422, "答案包含不存在的选项")
        previous = con.execute(
            "SELECT * FROM wrong_question_practices WHERE user_id=? AND wrong_question_id=? AND request_id=?",
            (user_id, question_id, str(payload.requestId)),
        ).fetchone()
        if previous is not None:
            if json.loads(previous["selected_json"]) != payload.selected:
                raise HTTPException(409, "本次练习已提交，请开始新一轮重练")
            result = practice_view(previous)
        else:
            practice_id = str(uuid4())
            con.execute(
                "INSERT INTO wrong_question_practices VALUES(?,?,?,?,?,?,?)",
                (practice_id, question_id, user_id, str(payload.requestId), dump(payload.selected),
                 int(set(payload.selected) == set(question["correct"])), now_iso()),
            )
            result = practice_view(con.execute(
                "SELECT * FROM wrong_question_practices WHERE id=? AND user_id=?", (practice_id, user_id),
            ).fetchone())
        return {"result": result, "item": detail_view(con, owned_question(con, question_id, user_id))}
