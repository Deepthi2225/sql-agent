import mysql.connector
from mysql.connector import Error
import os

import config


def get_connection(database_name: str | None = None):
    """Create and return a MySQL connection."""
    target_db = config.DB_NAME if database_name is None else database_name

    connect_kwargs = {
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
    }
    if target_db:
        connect_kwargs["database"] = target_db

    try:
        conn = mysql.connector.connect(**connect_kwargs)
        if conn.is_connected():
            return conn
    except Error as e:
        raise ConnectionError(f"Failed to connect to MySQL: {e}")


def list_databases() -> list[str]:
    """Return user-visible databases from the MySQL server."""
    conn = None
    cursor = None
    system_dbs = {"information_schema", "mysql", "performance_schema", "sys"}

    try:
        conn = get_connection(database_name="")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW DATABASES")
        rows = cursor.fetchall()
        names = [row.get("Database", "") for row in rows if row.get("Database")]
        return [name for name in names if name.lower() not in system_dbs]
    except Error as e:
        raise RuntimeError(f"Could not list databases: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def set_active_database(database_name: str) -> str:
    """Switch active database for this running process after validation."""
    selected = database_name.strip()
    if not selected:
        raise ValueError("Database name cannot be empty.")

    available = set(list_databases())
    if selected not in available:
        raise ValueError(f"Database '{selected}' is not available on this server.")

    config.DB_NAME = selected
    os.environ["DB_NAME"] = selected
    return selected


def _strip_delimiter(sql: str) -> tuple[str, bool]:
    """
    Remove DELIMITER directives that are MySQL CLI-only and not understood by
    mysql-connector-python.  Returns the cleaned SQL and whether it contains
    a DDL body (procedure / function / trigger / event) that must be executed
    with multi=True so the connector handles the compound statement correctly.
    """
    import re

    # Detect body-DDL keywords before stripping so we can flag multi-execution.
    body_ddl = bool(re.search(
        r"\b(CREATE|ALTER)\s+(DEFINER\s*=\s*\S+\s+)?"
        r"(PROCEDURE|FUNCTION|TRIGGER|EVENT)\b",
        sql, re.IGNORECASE
    ))

    # Remove lines that are purely DELIMITER directives, e.g.
    #   DELIMITER $$        -> drop
    #   DELIMITER ;         -> drop
    # Then replace the custom delimiter token (e.g. $$) used as a statement
    # terminator with nothing (the body itself ends with END).
    delimiter_re = re.compile(r"^\s*DELIMITER\s+(\S+)\s*$", re.IGNORECASE | re.MULTILINE)
    custom_delimiters = delimiter_re.findall(sql)

    # Strip all DELIMITER directive lines
    cleaned = delimiter_re.sub("", sql)

    # Replace any custom delimiter tokens (e.g. $$) used as terminators
    for delim in custom_delimiters:
        if delim != ";":
            escaped = re.escape(delim)
            cleaned = re.sub(escaped, "", cleaned)

    cleaned = cleaned.strip()
    return cleaned, body_ddl


def execute_query(sql: str, allow_multi: bool = False, params: tuple | None = None) -> dict:
    """
    Execute a SQL query and return results.

    Args:
        sql:         The SQL string to execute (use %s placeholders for params).
        allow_multi: Allow semicolon-separated multi-statement execution.
        params:      Optional tuple of parameter values for %s placeholders.

    Returns:
        {
            "success": bool,
            "rows": list[dict],       # SELECT results
            "affected": int,          # INSERT/UPDATE/DELETE row count
            "error": str | None,
        }
    """
    conn = None
    cursor = None

    # Strip DELIMITER directives (MySQL CLI-only) and detect body-DDL
    sql, is_body_ddl = _strip_delimiter(sql)
    if is_body_ddl:
        allow_multi = True

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        if allow_multi:
            total_affected = 0
            last_rows = []
            for res in cursor.execute(sql, multi=True):
                if res.with_rows:
                    last_rows = res.fetchall()
                else:
                    total_affected += max(res.rowcount, 0)

            conn.commit()
            return {
                "success": True,
                "rows": last_rows,
                "affected": total_affected if total_affected > 0 else len(last_rows),
                "error": None,
            }

        cursor.execute(sql, params)

        # DML statements need a commit
        if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
            conn.commit()
            return {
                "success": True,
                "rows": [],
                "affected": cursor.rowcount,
                "error": None,
            }

        rows = cursor.fetchall()
        return {
            "success": True,
            "rows": rows,
            "affected": len(rows),
            "error": None,
        }

    except Error as e:
        return {
            "success": False,
            "rows": [],
            "affected": 0,
            "error": str(e),
        }
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def test_connection() -> bool:
    """Quick connectivity check. Returns True if DB is reachable."""
    try:
        conn = get_connection()
        conn.close()
        return True
    except ConnectionError:
        return False