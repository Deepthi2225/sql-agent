import unittest
from unittest.mock import patch

from sql_generator import generate_sql


class TestSqlGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = {
            "customers": {
                "columns": [
                    {"name": "id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                    {"name": "first_name", "type": "varchar(255)", "nullable": False, "key": "", "extra": ""},
                    {"name": "last_name", "type": "varchar(255)", "nullable": False, "key": "", "extra": ""},
                    {"name": "email", "type": "varchar(255)", "nullable": False, "key": "", "extra": ""},
                    {"name": "city", "type": "varchar(100)", "nullable": True, "key": "", "extra": ""},
                    {"name": "country", "type": "varchar(100)", "nullable": True, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            },
            "employee": {
                "columns": [
                    {"name": "emp_id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                    {"name": "name", "type": "varchar(255)", "nullable": False, "key": "", "extra": ""},
                    {"name": "department", "type": "varchar(255)", "nullable": True, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            }
        }

    @patch("sql_generator.chat")
    def test_show_tables_uses_schema_query(self, mock_chat):
        sql = generate_sql("show all tables", self.schema)

        self.assertEqual(sql, "SHOW TABLES;")
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_show_tables_and_row_counts_uses_information_schema(self, mock_chat):
        sql = generate_sql("show all tables and row counts", self.schema)

        self.assertIn("FROM INFORMATION_SCHEMA.TABLES", sql)
        self.assertIn("TABLE_SCHEMA = DATABASE()", sql)
        self.assertTrue(sql.strip().endswith(";"))
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_simple_top_n_uses_deterministic_query(self, mock_chat):
        sql = generate_sql("top 5 customers", self.schema)

        self.assertIn("FROM customers c", sql)
        self.assertTrue(sql.strip().endswith(";"))
        self.assertIn("LIMIT 5;", sql)
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_semantic_top_n_still_uses_llm(self, mock_chat):
        mock_chat.return_value = "SELECT c.id FROM customers c ORDER BY c.id DESC LIMIT 5;"

        sql = generate_sql("top 5 customers by revenue", self.schema)

        self.assertEqual(sql, "SELECT c.id FROM customers c ORDER BY c.id DESC LIMIT 5;")
        mock_chat.assert_called_once()

    @patch("sql_generator.chat")
    def test_show_rows_from_table_desc_uses_deterministic_query(self, mock_chat):
        sql = generate_sql("show rows from employee sorted in descending order", self.schema)

        self.assertIn("FROM employee e", sql)
        self.assertIn("ORDER BY e.emp_id DESC", sql)
        self.assertIn("LIMIT 10;", sql)
        self.assertTrue(sql.strip().endswith(";"))
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_show_all_rows_from_table_skips_default_limit(self, mock_chat):
        sql = generate_sql("show all rows from employee", self.schema)

        self.assertIn("SELECT *", sql)
        self.assertIn("FROM employee", sql)
        self.assertNotIn("LIMIT 10", sql)
        self.assertTrue(sql.strip().endswith(";"))
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_show_rows_from_table_with_explicit_limit_uses_requested_limit(self, mock_chat):
        sql = generate_sql("show rows from employee limit 3", self.schema)

        self.assertIn("FROM employee e", sql)
        self.assertIn("LIMIT 3;", sql)
        self.assertTrue(sql.strip().endswith(";"))
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_duplicate_email_uses_deterministic_grouping(self, mock_chat):
        sql = generate_sql("find duplicate email addresses", self.schema)

        self.assertIn("GROUP BY", sql)
        self.assertIn("HAVING COUNT(*) > 1", sql)
        self.assertIn("email", sql.lower())
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_recent_records_uses_deterministic_limit(self, mock_chat):
        schema = {
            "events": {
                "columns": [
                    {"name": "id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                    {"name": "created_at", "type": "datetime", "nullable": False, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            }
        }

        sql = generate_sql("list the 10 most recently created records", schema)

        self.assertIn("FROM events", sql)
        self.assertIn("ORDER BY created_at DESC", sql)
        self.assertIn("LIMIT 10;", sql)
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_count_by_uses_grouping_when_table_and_column_exist(self, mock_chat):
        schema = {
            "employees": {
                "columns": [
                    {"name": "id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                    {"name": "role", "type": "varchar(50)", "nullable": False, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            }
        }

        sql = generate_sql("count employees by role", schema)

        self.assertIn("FROM employees", sql)
        self.assertIn("GROUP BY", sql)
        self.assertIn("COUNT(*) AS total_count", sql)
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_top_n_unknown_table_fails_fast(self, mock_chat):
        with self.assertRaises(ValueError):
            generate_sql("top 5 suppliers", self.schema)

        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_artist_exhibition_prompt_uses_deterministic_join(self, mock_chat):
        schema = {
            "artist_profile": {
                "columns": [
                    {"name": "artist_id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                    {"name": "first_name", "type": "varchar(50)", "nullable": False, "key": "", "extra": ""},
                    {"name": "last_name", "type": "varchar(50)", "nullable": False, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            },
            "artist_exhibition": {
                "columns": [
                    {"name": "artist_id", "type": "int", "nullable": False, "key": "", "extra": ""},
                    {"name": "exhibition_id", "type": "int", "nullable": False, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            },
            "exhibition": {
                "columns": [
                    {"name": "exhibition_id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                    {"name": "exhibition_name", "type": "varchar(100)", "nullable": False, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            },
        }

        sql = generate_sql("list artists with their exhibition names", schema)

        self.assertIn("FROM artist_exhibition", sql)
        self.assertIn("JOIN artist_profile", sql)
        self.assertIn("JOIN exhibition", sql)
        self.assertIn("AS exhibition_name", sql)
        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_count_by_unknown_entity_fails_fast(self, mock_chat):
        with self.assertRaises(ValueError):
            generate_sql("count suppliers by role", self.schema)

        mock_chat.assert_not_called()

    @patch("sql_generator.chat")
    def test_count_by_missing_column_fails_fast(self, mock_chat):
        with self.assertRaises(ValueError):
            generate_sql("count employee by role", self.schema)

        mock_chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
