from database import execute_query
import config


def get_schema() -> dict:
    """
    Fetch the full schema of the current database.

    Returns a dict like:
    {
        "users": {
            "columns": [
                {"name": "id", "type": "int", "nullable": False, "key": "PRI"},
                {"name": "email", "type": "varchar(255)", "nullable": False, "key": "UNI"},
            ],
            "foreign_keys": [
                {"column": "role_id", "references_table": "roles", "references_column": "id"}
            ]
        },
        ...
    }
    """
    tables = _get_tables()
    schema = {}
    for table in tables:
        schema[table] = {
            "columns": _get_columns(table),
            "foreign_keys": _get_foreign_keys(table),
        }
    return schema


def _get_tables() -> list[str]:
    sql = """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s
          AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """
    result = execute_query(sql, params=(config.DB_NAME,))
    if not result["success"]:
        raise RuntimeError(f"Could not fetch tables: {result['error']}")
    return [row["TABLE_NAME"] for row in result["rows"]]


def _get_columns(table: str) -> list[dict]:
    sql = """
        SELECT
            COLUMN_NAME   AS name,
            COLUMN_TYPE   AS type,
            IS_NULLABLE   AS nullable,
            COLUMN_KEY    AS key_type,
            COLUMN_DEFAULT AS default_val,
            EXTRA         AS extra
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME   = %s
        ORDER BY ORDINAL_POSITION
    """
    result = execute_query(sql, params=(config.DB_NAME, table))
    if not result["success"]:
        raise RuntimeError(f"Could not fetch columns for {table}: {result['error']}")

    columns = []
    for row in result["rows"]:
        columns.append({
            "name": row["name"],
            "type": row["type"],
            "nullable": row["nullable"] == "YES",
            "key": row["key_type"],
            "default": row["default_val"],
            "extra": row["extra"],
        })
    return columns


def _get_foreign_keys(table: str) -> list[dict]:
    sql = """
        SELECT
            kcu.COLUMN_NAME            AS column_name,
            kcu.REFERENCED_TABLE_NAME  AS ref_table,
            kcu.REFERENCED_COLUMN_NAME AS ref_column
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
        JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
          ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
         AND kcu.TABLE_SCHEMA    = tc.TABLE_SCHEMA
         AND kcu.TABLE_NAME      = tc.TABLE_NAME
        WHERE kcu.TABLE_SCHEMA  = %s
          AND kcu.TABLE_NAME    = %s
          AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
    """
    result = execute_query(sql, params=(config.DB_NAME, table))
    if not result["success"]:
        return []  # FK info is optional — don't crash

    return [
        {
            "column": row["column_name"],
            "references_table": row["ref_table"],
            "references_column": row["ref_column"],
        }
        for row in result["rows"]
    ]


def schema_to_prompt_text(schema: dict) -> str:
    """
    Convert schema dict into a compact, LLM-friendly text block.

    Example output:
        Table: users
          - id (int, PK, NOT NULL)
          - email (varchar(255), NOT NULL)
          - role_id (int, FK -> roles.id)
    """
    lines = []
    for table, info in schema.items():
        lines.append(f"Table: {table}")
        for col in info["columns"]:
            parts = [col["name"], col["type"]]
            if col["key"] == "PRI":
                parts.append("PK")
            if not col["nullable"]:
                parts.append("NOT NULL")
            if col["extra"]:
                parts.append(col["extra"])

            # annotate FK columns
            for fk in info["foreign_keys"]:
                if fk["column"] == col["name"]:
                    parts.append(f"FK -> {fk['references_table']}.{fk['references_column']}")

            lines.append("  - " + ", ".join(parts))
        lines.append("")
    return "\n".join(lines)