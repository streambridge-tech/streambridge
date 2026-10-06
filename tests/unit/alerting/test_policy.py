import unittest

from app.services.alerting.policy import first_match, parse_rules, validate_rules


class TestPolicy(unittest.TestCase):
    def test_fallback_single_rule(self):
        rules = parse_rules(None, "PAUSED", "re-trigger")
        self.assertEqual(rules, [{"rule": "PAUSED", "action": "re-trigger"}])

    def test_paused_cannot_pause(self):
        err = validate_rules([{"rule": "PAUSED", "action": "pause"}])
        self.assertTrue(err)

    def test_duplicate_rule_rejected(self):
        err = validate_rules([
            {"rule": "FAILED", "action": "pause"},
            {"rule": "FAILED", "action": "notify"},
        ])
        self.assertTrue(err)

    def test_first_match_skips_earlier_rules(self):
        rules = [
            {"rule": "FAILED", "action": "re-trigger"},
            {"rule": "PAUSED", "action": "notify"},
        ]
        idx, hit = first_match(rules, "PAUSED")
        self.assertEqual(idx, 1)
        self.assertEqual(hit["action"], "notify")
        idx, hit = first_match(rules, "RUNNING")
        self.assertIsNone(idx)
        self.assertIsNone(hit)


if __name__ == "__main__":
    unittest.main()
