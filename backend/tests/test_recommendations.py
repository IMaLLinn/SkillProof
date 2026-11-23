"""Exercise report-based learning suggestions through real sessions and submissions."""

import json
import unittest
from contextlib import closing
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.catalog import DIMENSION_IDS
from app.config import Settings
from app.db import connect
from app.main import create_app
from app.recommendations import read_resources


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        content = directory / "content"
        defaults = Settings()
        copytree(defaults.content_dir, content)
        self.resources = content / "learning-resources.json"
        self.settings = Settings(
            database_path=directory / "test.sqlite3",
            content_dir=content, environment="development", cookie_secure=False,
            allowed_hosts=("testserver",), origin=None,
        )
        self.app = create_app(self.settings)
        self.client = self.enterContext(TestClient(self.app))
        self.headers = self.register(self.client, "owner")

    def register(self, client, name):
        response = client.post("/api/auth/register", json={
            "email": f"{name}@example.invalid",
            "name": name,
            "password": "recommendation-test-password",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return {"X-CSRF-Token": response.json()["csrfToken"]}

    def create_attempt(self):
        response = self.client.post("/api/attempts", headers=self.headers, json={"roleId": "backend"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def submit(self, attempt, correct_counts):
        with closing(connect(self.settings)) as con:
            snapshot = con.execute(
                "SELECT questions_json FROM attempts WHERE id=?", (attempt["id"],),
            ).fetchone()[0]
        remaining = dict(zip(DIMENSION_IDS, correct_counts, strict=True))
        answers = {}
        for question in json.loads(snapshot):
            dimension = question["dimension"]
            if remaining[dimension]:
                answers[question["id"]] = question["correct"]
                remaining[dimension] -= 1
            else:
                wrong = next(option["id"] for option in question["options"]
                             if option["id"] not in question["correct"])
                answers[question["id"]] = [wrong]
        url = f'/api/attempts/{attempt["id"]}'
        saved = self.client.put(
            f"{url}/answers", headers=self.headers,
            json={"answers": answers, "expectedVersion": attempt["answersVersion"]},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        response = self.client.post(f"{url}/submit", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_all_six_dimensions_have_resources_with_ability_tree_topics(self):
        tree = json.loads((self.settings.content_dir / "ability-tree.json").read_text(encoding="utf-8"))
        catalog = read_resources(self.resources)
        self.assertEqual(set(catalog), set(DIMENSION_IDS))
        for dimension in tree["dimensions"]:
            self.assertTrue(dimension["description"])
            topics = {topic["id"]: topic["name"] for topic in dimension["topics"]}
            resources = catalog[dimension["id"]]
            self.assertGreaterEqual(len(resources), 2)
            self.assertEqual(len({item["topicId"] for item in resources}), len(resources))
            for resource in resources:
                self.assertEqual(topics[resource["topicId"]], resource["topic"])

    def test_matches_saved_report_order_and_includes_third_place_ties(self):
        # Deliberately put the two lowest scores later in the canonical dimension order.
        report = self.submit(self.create_attempt(), [2, 1, 0, 1, 0, 3])
        url = f'/api/reports/{report["id"]}/recommendations'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        items = response.json()["items"]
        self.assertEqual([item["id"] for item in items], ["database", "os", "algorithms", "network"])
        for item in items:
            self.assertTrue(item["description"])
            self.assertEqual(len(item["resources"]), 2)
            self.assertTrue(all(resource["topicId"].startswith(item["id"] + ".")
                                for resource in item["resources"]))

    def test_no_resources_and_full_score_return_empty(self):
        full = self.submit(self.create_attempt(), [3] * 6)
        self.assertEqual(self.client.get(f'/api/reports/{full["id"]}/recommendations').json(), {"items": []})
        weak = self.submit(self.create_attempt(), [0] * 6)
        self.resources.write_text("[]", encoding="utf-8")
        self.assertEqual(self.client.get(f'/api/reports/{weak["id"]}/recommendations').json(), {"items": []})

    def test_requires_login_ownership_and_submitted_result(self):
        attempt = self.create_attempt()
        url = f'/api/reports/{attempt["id"]}/recommendations'
        self.assertEqual(self.client.get(url).status_code, 409)
        self.assertEqual(self.client.get("/api/reports/missing/recommendations").status_code, 404)
        self.submit(attempt, [2] * 6)
        with TestClient(self.app) as other:
            self.assertEqual(other.get(url).status_code, 401)
            self.register(other, "other")
            self.assertEqual(other.get(url).status_code, 404)

    def test_unavailable_resources_do_not_block_submission_or_report(self):
        self.resources.unlink()
        report = self.submit(self.create_attempt(), [2] * 6)
        url = f'/api/reports/{report["id"]}'
        self.assertEqual(self.client.get(f"{url}/recommendations").status_code, 503)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), report)
