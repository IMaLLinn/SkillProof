"""Check saved answers, incomplete submission and reports through the public API."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from assessment_fixtures import DIMENSIONS, write_assessment_bank
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "assessment-acceptance-password"


class AssessmentAcceptanceTests(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        content = directory / "content"
        write_assessment_bank(content)
        self.settings = Settings(
            database_path=directory / "assessment.sqlite3", content_dir=content,
            environment="development", cookie_secure=False,
            allowed_hosts=("testserver",), origin="http://testserver",
        )

    def client(self):
        return TestClient(create_app(self.settings), headers={"Origin": "http://testserver"})

    def assert_draft(self, response, answers):
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()
        self.assertEqual(draft["status"], "in_progress")
        self.assertIsNone(draft["submittedAt"])
        self.assertEqual(draft["questionCount"], 18)
        self.assertEqual(draft["answeredCount"], len(answers))
        self.assertEqual(
            {key: set(value) for key, value in draft["answers"].items()},
            {key: set(value) for key, value in answers.items()},
        )
        return draft

    def test_saved_draft_survives_rejected_submission_and_completes_with_correct_report(self):
        # Fixed choices are independent of the returned questions and the scorer.
        answers = {
            "programming-easy-1": ["A"], "programming-easy-2": ["B"],
            "programming-medium": ["A", "C"],
            "algorithms-easy-1": ["A"], "algorithms-easy-2": ["D"],
            "algorithms-medium": ["B", "D"],
            "database-easy-1": ["A"], "database-easy-2": ["B"],
            "database-medium": ["A"],
            "network-easy-1": ["D"], "network-easy-2": ["A"],
            "network-medium": ["C", "A"],
            "os-easy-1": ["D"], "os-easy-2": ["A"], "os-medium": ["A"],
            "software-easy-1": ["D"], "software-easy-2": ["A"],
        }
        credentials = {"email": "assessment@example.invalid", "password": PASSWORD}
        with self.client() as client:
            registered = client.post("/api/auth/register", json={**credentials, "name": "流程验收"})
            self.assertEqual(registered.status_code, 201, registered.text)
            headers = {"X-CSRF-Token": registered.json()["csrfToken"]}
            created = self.assert_draft(
                client.post("/api/attempts", json={"roleId": "backend"}, headers=headers), {},
            )
            expected_ids = {
                f"{dimension}-{suffix}" for dimension, _ in DIMENSIONS
                for suffix in ("easy-1", "easy-2", "medium")
            }
            self.assertEqual(len(created["questions"]), 18)
            self.assertEqual({question["id"] for question in created["questions"]}, expected_ids)
            url = f"/api/attempts/{created['id']}"
            report_url = f"/api/reports/{created['id']}"
            self.assertEqual(created["answersVersion"], 0)
            saved = self.assert_draft(client.put(
                f"{url}/answers", json={"answers": answers, "expectedVersion": created["answersVersion"]},
                headers=headers,
            ), answers)
            self.assertEqual(saved["answersVersion"], 1)

        # 重新登录，检查上次保存的草稿。
        with self.client() as client:
            logged_in = client.post("/api/auth/login", json=credentials)
            self.assertEqual(logged_in.status_code, 200, logged_in.text)
            headers = {"X-CSRF-Token": logged_in.json()["csrfToken"]}
            self.assert_draft(client.get(url), answers)
            resumed = self.assert_draft(
                client.post("/api/attempts", json={"roleId": "backend"}, headers=headers), answers,
            )
            self.assertEqual(resumed["id"], created["id"])
            self.assertEqual(resumed["answersVersion"], 1)

            rejected = client.post(f"{url}/submit", headers=headers)
            self.assertEqual(rejected.status_code, 422, rejected.text)
            self.assert_draft(client.get(url), answers)
            self.assertEqual(client.get(report_url).status_code, 409)

            last_answer = {"software-medium": ["C", "A"]}
            completed_answers = {**answers, **last_answer}
            completed = self.assert_draft(
                client.put(f"{url}/answers", json={
                    "answers": last_answer, "expectedVersion": resumed["answersVersion"],
                }, headers=headers),
                completed_answers,
            )
            self.assertEqual(completed["answersVersion"], 2)
            submitted = client.post(f"{url}/submit", headers=headers)
            self.assertEqual(submitted.status_code, 200, submitted.text)
            report = submitted.json()
            self.assertEqual((report["id"], report["roleId"], report["roleName"]),
                             (created["id"], "backend", "后端开发"))
            self.assertEqual(report["createdAt"], created["createdAt"])
            self.assertTrue(report["submittedAt"])
            # Correct weights by dimension: 4 + 1 + 2 + 2 + 0 + 2 = 11, out of 24.
            self.assertEqual(report["score"], 45.83)
            self.assertEqual((report["correctCount"], report["questionCount"]), (8, 18))
            self.assertEqual(len(report["dimensions"]), 6)
            self.assertEqual(
                {item["id"]: (item["score"], item["correct"], item["total"]) for item in report["dimensions"]},
                {"programming": (100, 3, 3), "algorithms": (33.33, 1, 3),
                 "database": (66.67, 2, 3), "network": (33.33, 1, 3),
                 "os": (0, 0, 3), "software": (33.33, 1, 3)},
            )
            self.assertEqual(
                [item["id"] for item in report["weakDimensions"]],
                ["os", "algorithms", "network", "software", "database"],
            )
            queried = client.get(report_url)
            self.assertEqual(queried.status_code, 200, queried.text)
            self.assertEqual(queried.json(), report)
            final = client.get(url)
            self.assertEqual(final.status_code, 200, final.text)
            final_attempt = final.json()
            self.assertEqual(final_attempt["status"], "submitted")
            self.assertEqual(final_attempt["answersVersion"], 2)
            self.assertEqual(final_attempt["answeredCount"], 18)
            self.assertEqual(final_attempt["submittedAt"], report["submittedAt"])
            self.assertEqual(
                {key: set(value) for key, value in final_attempt["answers"].items()},
                {key: set(value) for key, value in completed_answers.items()},
            )


if __name__ == "__main__":
    unittest.main()
