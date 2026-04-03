import unittest
from unittest.mock import patch

import controller


class TestController(unittest.TestCase):
    @patch("controller.execute_query")
    @patch("controller._correction_loop")
    @patch("controller.validate_sql")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_no_double_execute_after_validation_correction(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_correction_loop,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "SELECT bad_sql"
        mock_validate_sql.return_value = {
            "valid": False,
            "errors": ["syntax issue"],
            "warnings": [],
        }

        def _mark_success(user_request, sql, error, schema, result, intent_policy, confirmed, execute):
            result.success = True
            result.sql = "SELECT 1;"
            result.rows = [{"x": 1}]
            result.affected_rows = 1
            return "SELECT 1;"

        mock_correction_loop.side_effect = _mark_success

        result = controller.run_query("test request")

        self.assertTrue(result.success)
        self.assertEqual(result.sql, "SELECT 1;")
        mock_execute_query.assert_not_called()

    @patch("controller.execute_query")
    @patch("controller.validate_sql")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_execute_called_once_on_clean_path(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "SELECT c.id FROM customers c;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_execute_query.return_value = {
            "success": True,
            "rows": [{"id": 1}],
            "affected": 1,
            "error": None,
        }

        result = controller.run_query("list customers")

        self.assertTrue(result.success)
        self.assertEqual(result.affected_rows, 1)
        mock_execute_query.assert_called_once()

    @patch("controller.execute_query")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_explicit_unknown_table_fails_fast(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {
            "customers": {"columns": [], "foreign_keys": []},
            "orders": {"columns": [], "foreign_keys": []},
        }

        result = controller.run_query("show rows from employee sorted in descending order")

        self.assertFalse(result.success)
        self.assertIn("does not exist", result.error)
        mock_generate_sql.assert_not_called()
        mock_execute_query.assert_not_called()

    @patch("controller.execute_query")
    @patch("controller.validate_sql")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_dry_run_returns_preview_without_execution(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "SELECT c.id FROM customers c;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}

        result = controller.run_query("list customers", execute=False)

        self.assertTrue(result.success)
        self.assertEqual(result.sql, "SELECT c.id FROM customers c;")
        self.assertEqual(result.operation_type, "read")
        self.assertEqual(result.risk_level, "low")
        self.assertFalse(result.requires_confirmation)
        mock_execute_query.assert_not_called()

    @patch("controller.execute_query")
    @patch("controller.validate_sql")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_high_risk_requires_confirmation(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "DROP TABLE customers;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}

        result = controller.run_query("drop customers table", confirmed=False)

        self.assertFalse(result.success)
        self.assertIn("requires confirmation", result.error)
        self.assertEqual(result.risk_level, "critical")
        self.assertTrue(result.requires_confirmation)
        mock_execute_query.assert_not_called()

    @patch("controller.execute_query")
    @patch("controller.validate_sql")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_dangerous_intent_still_requires_confirmation_if_sql_drifts(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"orders": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "DELETE FROM orders WHERE id = 1;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}

        result = controller.run_query("drop table orders", confirmed=False)

        self.assertFalse(result.success)
        self.assertIn("requires confirmation", result.error)
        self.assertEqual(result.intent_risk_level, "critical")
        self.assertTrue(result.requires_confirmation)
        mock_execute_query.assert_not_called()

    @patch("controller.execute_query")
    @patch("controller.validate_sql")
    @patch("controller.correct_sql")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_dry_run_validation_correction_does_not_execute(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_correct_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {
            "customers": {
                "columns": [
                    {"name": "id", "key": "PRI"},
                    {"name": "email", "key": ""},
                ],
                "foreign_keys": [],
            }
        }
        mock_generate_sql.return_value = "SELECT c.bad_col FROM customers c;"
        mock_correct_sql.return_value = "SELECT c.id, c.email FROM customers c;"
        mock_validate_sql.side_effect = [
            {"valid": False, "errors": ["Column 'c.bad_col' does not exist in table 'customers'."], "warnings": []},
            {"valid": True, "errors": [], "warnings": []},
        ]

        result = controller.run_query("list customers", execute=False)

        self.assertTrue(result.success)
        self.assertEqual(result.sql, "SELECT c.id, c.email FROM customers c;")
        mock_execute_query.assert_not_called()

    @patch("controller._correction_loop")
    @patch("controller.execute_query")
    @patch("controller.validate_sql")
    @patch("controller.generate_sql")
    @patch("controller.get_schema")
    def test_drop_intent_ddl_block_fails_fast_without_correction(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
        mock_correction_loop,
    ):
        mock_get_schema.return_value = {"orders": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "DROP TABLE orders;"
        mock_validate_sql.return_value = {
            "valid": False,
            "errors": ["DDL statements are blocked by default (DROP/TRUNCATE/ALTER/CREATE/RENAME)."],
            "warnings": [],
        }

        result = controller.run_query("drop table orders", execute=False, confirmed=False)

        self.assertFalse(result.success)
        self.assertIn("DDL statements are blocked", result.error)
        mock_correction_loop.assert_not_called()
        mock_execute_query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
