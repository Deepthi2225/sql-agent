import unittest

from validator import validate_sql


class TestValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = {
            "customers": {
                "columns": [
                    {"name": "id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                    {"name": "email", "type": "varchar(255)", "nullable": False, "key": "", "extra": ""},
                ],
                "foreign_keys": [],
            },
            "orders": {
                "columns": [
                    {"name": "id", "type": "int", "nullable": False, "key": "PRI", "extra": ""},
                ],
                "foreign_keys": [],
            },
        }

    def test_blocks_update_without_where(self):
        result = validate_sql("UPDATE customers SET city = 'Pune';", self.schema)
        self.assertFalse(result["valid"])
        self.assertTrue(any("WHERE" in err for err in result["errors"]))

    def test_blocks_ddl_by_default(self):
        result = validate_sql("DROP TABLE customers;", self.schema)
        self.assertFalse(result["valid"])
        self.assertTrue(any("DDL" in err for err in result["errors"]))

    def test_allows_ddl_with_override(self):
        result = validate_sql("DROP TABLE customers;", self.schema, allow_ddl_override=True)
        self.assertTrue(result["valid"])

    def test_blocks_multi_statement_by_default(self):
        result = validate_sql("SELECT id FROM customers; SELECT id FROM orders;", self.schema)
        self.assertFalse(result["valid"])
        self.assertTrue(any("Multiple SQL statements" in err for err in result["errors"]))

    def test_allows_multi_statement_with_override(self):
        result = validate_sql(
            "SELECT id FROM customers; SELECT id FROM orders;",
            self.schema,
            allow_multi_override=True,
        )
        self.assertTrue(result["valid"])

    def test_allows_simple_select(self):
        result = validate_sql("SELECT c.id FROM customers c;", self.schema)
        self.assertTrue(result["valid"])

    def test_blocks_unknown_column_reference(self):
        result = validate_sql("SELECT c.missing_col FROM customers c;", self.schema)
        self.assertFalse(result["valid"])
        self.assertTrue(any("does not exist" in err for err in result["errors"]))

    def test_allows_information_schema_tables_query(self):
        result = validate_sql(
            "SELECT t.TABLE_NAME FROM INFORMATION_SCHEMA.TABLES t WHERE t.TABLE_SCHEMA = DATABASE();",
            self.schema,
        )
        self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()
