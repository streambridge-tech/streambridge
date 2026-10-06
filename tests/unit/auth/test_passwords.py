import unittest

from app.utils.passwords import (
    MIN_PASSWORD_LEN,
    hash_password,
    password_error,
    verify_password,
)


class PasswordHashingTests(unittest.TestCase):
    def test_hash_is_not_plaintext_and_verifies(self):
        h = hash_password("correct horse battery")
        self.assertNotIn("correct horse battery", h)
        self.assertTrue(h.startswith("$argon2"))
        self.assertTrue(verify_password(h, "correct horse battery"))

    def test_wrong_password_fails(self):
        h = hash_password("correct horse battery")
        self.assertFalse(verify_password(h, "wrong"))

    def test_hashes_are_salted_and_unique(self):
        self.assertNotEqual(hash_password("same-pass-value"), hash_password("same-pass-value"))

    def test_verify_handles_garbage_hash(self):
        self.assertFalse(verify_password("not-a-hash", "anything"))

    def test_password_error_rules(self):
        self.assertIsNotNone(password_error(""))
        self.assertIsNotNone(password_error("x" * (MIN_PASSWORD_LEN - 1)))
        self.assertIsNone(password_error("x" * MIN_PASSWORD_LEN))


if __name__ == "__main__":
    unittest.main()
