import unittest

from pydantic import ValidationError

from app.models import ProfileInput
from app.catalog import ROLE_MAP


class InputModelTests(unittest.TestCase):
    def test_profile_rejects_unknown_target_role(self):
        known_role = next(iter(ROLE_MAP))
        self.assertEqual(ProfileInput(name="张三", targetRole=known_role).targetRole, known_role)
        with self.assertRaises(ValidationError):
            ProfileInput(name="张三", targetRole="not-a-role")


if __name__ == "__main__":
    unittest.main()
