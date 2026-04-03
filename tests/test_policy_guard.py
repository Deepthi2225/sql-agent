import unittest

from policy_guard import authorize_request


class TestPolicyGuard(unittest.TestCase):
    def test_viewer_cannot_execute_write(self):
        decision = authorize_request("viewer", "write", "medium", True, False)
        self.assertFalse(decision.allowed)

    def test_operator_cannot_execute_critical(self):
        decision = authorize_request("operator", "schema", "critical", True, True)
        self.assertFalse(decision.allowed)

    def test_admin_can_execute_critical_when_confirmed(self):
        decision = authorize_request("admin", "schema", "critical", True, True)
        self.assertTrue(decision.allowed)

    def test_dry_run_allowed_for_any_role(self):
        decision = authorize_request("viewer", "schema", "critical", False, False)
        self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main()
