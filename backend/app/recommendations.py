"""Match learning resources to the weak dimensions of a saved assessment."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .catalog import DIMENSION_IDS
from .reports import read_report
from .security import Principal, get_db, require_user
from .url_validation import https_url

router = APIRouter(prefix="/api", tags=["reports"])
LOGGER = logging.getLogger("skillproof")
RESOURCE_FIELDS = ("topicId", "topic", "title", "summary", "source", "url", "exercise", "expectedResult")


def read_resources(path: Path) -> dict[str, list[dict]]:
    """Read the optional catalog only when the recommendations endpoint is called."""
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            raise ValueError("Expected a resource list")

        by_dimension: dict[str, list[dict]] = {}
        for entry in entries:
            if not isinstance(entry, dict) or any(
                not isinstance(entry.get(field), str) or not entry[field].strip()
                for field in RESOURCE_FIELDS
            ):
                raise ValueError("Incomplete learning resource")
            dimension, separator, topic = entry["topicId"].partition(".")
            if not separator or not topic or dimension not in DIMENSION_IDS:
                raise ValueError("Unknown learning resource dimension")
            https_url(entry["url"])
            by_dimension.setdefault(dimension, []).append(
                {field: entry[field] for field in RESOURCE_FIELDS}
            )
        return by_dimension
    except (OSError, ValueError) as exc:
        LOGGER.warning("Learning resources unavailable: %s", type(exc).__name__)
        raise HTTPException(503, "学习资源暂时不可用，请稍后重试") from exc


def visible_weak_ids(report: dict) -> list[str]:
    weak = report.get("weakDimensions")
    if not isinstance(weak, list):
        raise HTTPException(500, "结果快照缺少薄弱维度")
    for item in weak:
        if (
            not isinstance(item, dict)
            or item.get("id") not in DIMENSION_IDS
            or type(item.get("correct")) is not int
            or type(item.get("total")) is not int
            or not 0 <= item["correct"] <= item["total"]
            or item["total"] == 0
        ):
            raise HTTPException(500, "结果快照中的薄弱维度无效")

    # Keep the report order and all dimensions tied with the third item.
    if len(weak) <= 3:
        return [item["id"] for item in weak]
    third = weak[2]
    result = [item["id"] for item in weak[:3]]
    for item in weak[3:]:
        if item["correct"] * third["total"] != third["correct"] * item["total"]:
            break
        result.append(item["id"])
    return result


@router.get("/reports/{attempt_id}/recommendations")
def get_recommendations(
    attempt_id: str,
    request: Request,
    principal: Principal = Depends(require_user),
    connection=Depends(get_db),
) -> dict:
    report = read_report(connection, attempt_id, principal.user["id"])
    weak_ids = visible_weak_ids(report)
    if not weak_ids:
        return {"items": []}

    by_dimension = read_resources(request.app.state.settings.content_dir / "learning-resources.json")
    dimensions = {item["id"]: item for item in request.app.state.catalog["dimensions"]}
    return {
        "items": [
            {**dimensions[key], "resources": by_dimension[key][:2]}
            for key in weak_ids if key in by_dimension
        ],
    }
