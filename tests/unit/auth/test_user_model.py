import unittest

from app.models.user import User, normalize_username, valid_username


class UsernameTests(unittest.TestCase):
    def test_normalize_lowercases_and_trims(self):
        self.assertEqual(normalize_username("  Ana@Corp.com "), "ana@corp.com")

    def test_valid_username(self):
        self.assertTrue(valid_username("ana@corp.com"))
        self.assertTrue(valid_username("ravi.k"))

    def test_invalid_username(self):
        self.assertFalse(valid_username("ab"))          # too short
        self.assertFalse(valid_username("has space"))   # space
        self.assertFalse(valid_username(""))


class UserModelTests(unittest.TestCase):
    def test_set_and_check_password(self):
        u = User(username="ana@corp.com")
        u.set_password("launch-ready-pass")
        self.assertTrue(u.check_password("launch-ready-pass"))
        self.assertFalse(u.check_password("nope"))

    def test_public_dict_hides_hash(self):
        u = User(username="ana@corp.com", active=True, is_admin=True)
        u.set_password("launch-ready-pass")
        d = u.to_public_dict()
        self.assertNotIn("password_hash", d)
        self.assertNotIn("passwordHash", d)
        self.assertEqual(d["username"], "ana@corp.com")
        self.assertTrue(d["isAdmin"])


if __name__ == "__main__":
    unittest.main()
