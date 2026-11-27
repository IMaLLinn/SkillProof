"""Wrongbook acceptance through real sessions, scoring, persistence and HTTP routes."""

import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, dump, initialize
from app.main import create_app


class WrongbookTests(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        self.settings = Settings(database_path=directory / "test.db", allowed_hosts=("testserver",),
                                 environment="development", cookie_secure=False, origin=None)
        self.app = create_app(self.settings)
        self.client = self.enterContext(TestClient(self.app))
        self.headers = self.register(self.client, "owner")

    def register(self, client, name):
        response = client.post("/api/auth/register", json={
            "email": f"{name}@example.invalid", "name": name, "password": "wrongbook-test-password",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return {"X-CSRF-Token": response.json()["csrfToken"]}

    def prepared_attempt(self):
        response = self.client.post("/api/attempts", json={"roleId": "backend"}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        attempt = response.json()
        with closing(connect(self.settings)) as con:
            questions = json.loads(con.execute("SELECT questions_json FROM attempts WHERE id=?", (attempt["id"],)).fetchone()[0])
            # Deterministic, valid answer sets in the temporary attempt snapshot.
            for question in questions:
                question["type"], question["correct"] = "single", ["A"]
            questions[0]["type"], questions[0]["correct"] = "multiple", ["A", "C"]
            con.execute("UPDATE attempts SET questions_json=? WHERE id=?", (dump(questions), attempt["id"]))
        return attempt, questions

    def submit(self, wrong_count=2):
        attempt, questions = self.prepared_attempt()
        answers = {q["id"]: q["correct"] for q in questions}
        for q in questions[:wrong_count]:
            # Selecting only A on the multiple-choice question must count as wrong.
            answers[q["id"]] = ["A"] if q["type"] == "multiple" else ["B"]
        response = self.client.put(f'/api/attempts/{attempt["id"]}/answers', headers=self.headers,
                                   json={"answers": answers, "expectedVersion": attempt["answersVersion"]})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post(f'/api/attempts/{attempt["id"]}/submit', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return attempt, questions, response.json()

    def items(self, **filters):
        response = self.client.get("/api/wrong-questions", params={"status": "all", **filters})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def practice(self, item, selected, request_id=None):
        return self.client.post(f'/api/wrong-questions/{item["id"]}/practice', headers=self.headers,
                                json={"selected": selected, "requestId": request_id or str(uuid4())})

    def test_collects_only_wrong_answers_and_does_not_leak_active_solutions(self):
        active, _ = self.prepared_attempt()
        self.assertEqual(self.items()["total"], 0)
        restored = self.client.get(f'/api/attempts/{active["id"]}').json()
        for question in restored["questions"]:
            self.assertNotIn("correct", question)
            self.assertNotIn("explanation", question)
        # Complete this existing draft rather than creating another active record.
        attempt, questions, report = self.submit()
        self.assertEqual(active["id"], attempt["id"])
        data = self.items()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["counts"], {"all": 2, "review": 2, "mastered": 0})
        self.assertEqual({i["questionId"] for i in data["items"]}, {q["id"] for q in questions[:2]})
        detail = self.client.get(f'/api/wrong-questions/{data["items"][0]["id"]}').json()
        self.assertEqual(detail["question"]["id"], detail["questionId"])
        self.assertTrue(detail["question"]["explanation"])
        self.assertEqual(detail["attemptId"], report["id"])
        self.assertNotEqual(set(detail["originalAnswer"]), set(detail["question"]["correct"]))
        self.assertEqual(self.client.get("/api/wrong-questions").headers["cache-control"], "no-store")

    def test_all_correct_submits_empty_wrongbook(self):
        self.submit(0)
        self.assertEqual(self.items()["items"], [])

    def test_duplicate_and_concurrent_submission_collect_once(self):
        attempt, _, report = self.submit(3)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.client.post(
                f'/api/attempts/{attempt["id"]}/submit', headers=self.headers), range(2)))
        for response in responses:
            self.assertEqual(response.json(), report)
        self.assertEqual(self.items()["total"], 3)

    def test_practice_exact_sets_idempotency_and_no_report_changes(self):
        attempt, questions, report = self.submit()
        with closing(connect(self.settings)) as con:
            before = tuple(con.execute("SELECT * FROM attempts WHERE id=?", (attempt["id"],)).fetchone())
        multiple = next(i for i in self.items()["items"] if i["questionId"] == questions[0]["id"])
        first = self.practice(multiple, ["A"]).json()
        self.assertFalse(first["result"]["isCorrect"])
        request_id = str(uuid4())
        correct = self.practice(multiple, ["C", "A"], request_id).json()
        self.assertTrue(correct["result"]["isCorrect"])
        self.assertFalse(correct["item"]["mastered"])
        repeated = self.practice(multiple, ["A", "C"], request_id).json()
        self.assertEqual(repeated["result"], correct["result"])
        self.assertEqual(repeated["item"]["practiceCount"], 2)
        self.assertEqual(self.practice(multiple, ["B"], request_id).status_code, 409)
        self.assertEqual(self.client.get(f'/api/reports/{attempt["id"]}').json(), report)
        with closing(connect(self.settings)) as con:
            after = tuple(con.execute("SELECT * FROM attempts WHERE id=?", (attempt["id"],)).fetchone())
        self.assertEqual(before, after)

    def test_concurrent_retry_counts_one_practice(self):
        self.submit(1)
        item = self.items()["items"][0]
        request_id = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.practice(item, ["A", "C"], request_id), range(2)))
        self.assertTrue(all(r.status_code == 200 for r in responses))
        self.assertEqual(responses[0].json()["result"]["id"], responses[1].json()["result"]["id"])
        self.assertEqual(self.client.get(f'/api/wrong-questions/{item["id"]}').json()["practiceCount"], 1)

    def test_mastery_relogin_restart_and_move_back(self):
        self.submit(1)
        item = self.items()["items"][0]
        self.practice(item, ["A", "C"])
        url = f'/api/wrong-questions/{item["id"]}'
        saved = self.client.patch(url, headers=self.headers, json={"mastered": True})
        self.assertTrue(saved.json()["mastered"])
        self.assertEqual(self.client.get("/api/wrong-questions").json()["total"], 0)
        initialize(self.settings)
        with TestClient(create_app(self.settings)) as restarted:
            login = restarted.post("/api/auth/login", json={"email": "owner@example.invalid", "password": "wrongbook-test-password"})
            self.assertEqual(login.status_code, 200)
            detail = restarted.get(url).json()
            self.assertTrue(detail["mastered"])
            self.assertEqual(detail["practiceCount"], 1)
            self.assertEqual(detail["practices"][0]["selected"], ["A", "C"])
            restored = restarted.patch(url, headers={"X-CSRF-Token": login.json()["csrfToken"]}, json={"mastered": False})
            self.assertFalse(restored.json()["mastered"])
            self.assertEqual(restarted.get("/api/wrong-questions").json()["total"], 1)

    def test_user_isolation_for_list_detail_practice_mastery(self):
        self.submit(1)
        item = self.items()["items"][0]
        url = f'/api/wrong-questions/{item["id"]}'
        with TestClient(self.app) as other:
            self.assertEqual(other.get("/api/wrong-questions").status_code, 401)
            headers = self.register(other, "other")
            self.assertEqual(other.get("/api/wrong-questions").json()["total"], 0)
            self.assertEqual(other.get(url).status_code, 404)
            self.assertEqual(other.patch(url, headers=headers, json={"mastered": True}).status_code, 404)
            self.assertEqual(other.post(url + "/practice", headers=headers,
                                        json={"selected": ["A"], "requestId": str(uuid4())}).status_code, 404)
        self.assertEqual(self.client.post(url + "/practice", json={"selected": ["A"], "requestId": str(uuid4())}).status_code, 403)
        detail = self.client.get(url).json()
        self.assertEqual(detail["practiceCount"], 0)
        self.assertFalse(detail["mastered"])

    def test_filters_pagination_and_query_validation(self):
        self.submit(5)
        data = self.items()
        item = data["items"][0]
        filtered = self.items(roleId=item["roleId"], dimension=item["dimension"], topicId=item["topicId"])
        self.assertTrue(all(i["topicId"] == item["topicId"] for i in filtered["items"]))
        self.assertEqual(self.items(roleId="no-such-role")["total"], 0)
        one = self.items(limit=1)
        two = self.items(limit=1, offset=1)
        self.assertEqual(one["total"], 5)
        self.assertNotEqual(one["items"][0]["id"], two["items"][0]["id"])
        for params in ({"dimension": "unknown"}, {"status": "unknown"}, {"limit": 101}, {"offset": -1}):
            self.assertEqual(self.client.get("/api/wrong-questions", params=params).status_code, 422)

    def test_invalid_practice_and_mastery_leave_storage_unchanged(self):
        self.submit(2)
        single = next(i for i in self.items()["items"] if i["type"] == "single")
        url = f'/api/wrong-questions/{single["id"]}'
        for selected in ([], ["A", "B"], ["Z"], ["A", "A"]):
            self.assertEqual(self.practice(single, selected).status_code, 422)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={"mastered": "true"}).status_code, 422)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={"mastered": True, "userId": "other"}).status_code, 422)
        self.assertEqual(self.client.get(url).json()["practiceCount"], 0)

    def test_collection_failure_rolls_back_submission(self):
        attempt, questions = self.prepared_attempt()
        saved = self.client.put(f'/api/attempts/{attempt["id"]}/answers', headers=self.headers,
                                json={"answers": {q["id"]: ["B"] for q in questions}, "expectedVersion": 0})
        self.assertEqual(saved.status_code, 200)
        with patch("app.api_assessments.collect_wrong_questions", side_effect=sqlite3.OperationalError("test failure")):
            response = self.client.post(f'/api/attempts/{attempt["id"]}/submit', headers=self.headers)
        self.assertEqual(response.status_code, 503)
        with closing(connect(self.settings)) as con:
            row = con.execute("SELECT status,report_json,answers_json FROM attempts WHERE id=?", (attempt["id"],)).fetchone()
        self.assertEqual(row["status"], "in_progress")
        self.assertIsNone(row["report_json"])
        self.assertEqual(len(json.loads(row["answers_json"])), 18)
        self.assertEqual(self.items()["total"], 0)

    def test_question_snapshot_survives_bank_changes_and_later_attempts(self):
        attempt, questions, report = self.submit(1)
        item = self.items()["items"][0]
        url = f'/api/wrong-questions/{item["id"]}'
        before = self.client.get(url).json()
        with closing(connect(self.settings)) as con:
            altered = {**questions[0], "stem": "changed after submission", "correct": ["B", "D"], "version": 99}
            con.execute("UPDATE questions SET content_json=? WHERE id=?", (dump(altered), questions[0]["id"]))
        self.assertEqual(self.client.get(url).json(), before)
        self.assertTrue(self.practice(item, ["A", "C"]).json()["result"]["isCorrect"])
        self.submit(1)
        self.assertEqual(self.items()["total"], 2)
        self.assertEqual(self.client.get(f'/api/reports/{attempt["id"]}').json(), report)

    def test_upgrading_existing_database_keeps_old_attempts_and_is_repeatable(self):
        # A database from the previous release has migrations 1..4 and no wrongbook tables.
        attempt, _, report = self.submit(1)
        with closing(connect(self.settings)) as con:
            con.execute("DROP TABLE wrong_question_practices")
            con.execute("DROP TABLE wrong_questions")
            con.execute("DELETE FROM schema_migrations WHERE version=5")
        initialize(self.settings)
        initialize(self.settings)
        with closing(connect(self.settings)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=5").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM wrong_questions").fetchone()[0], 0)
        self.assertEqual(self.client.get(f'/api/reports/{attempt["id"]}').json(), report)
