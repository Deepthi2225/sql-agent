import re
import sqlparse
from config import ALLOW_DDL, ALLOW_MULTI_STATEMENTS


def validate_sql(
    sql: str,
    schema: dict,
    allow_ddl_override: bool = False,
    allow_multi_override: bool = False,
) -> dict:
    """
    Run pre-execution checks on a generated SQL query.

    Returns:
        {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str],
        }
    """
    errors = []
    warnings = []

    if not sql or not sql.strip():
        return {"valid": False, "errors": ["SQL is empty."], "warnings": []}

    # 1. Parse check — sqlparse will flag broken syntax
    parsed = sqlparse.parse(sql.strip())
    statements = [stmt.value.strip() for stmt in parsed if stmt and stmt.value.strip()]
    if not statements:
        errors.append("Could not parse SQL statement.")
        return {"valid": False, "errors": errors, "warnings": warnings}

    multi_allowed = ALLOW_MULTI_STATEMENTS or allow_multi_override
    if len(statements) > 1 and not multi_allowed:
        errors.append("Multiple SQL statements are not allowed.")

    primary_sql = statements[0]

    sql_upper = primary_sql.upper()

    # 2. Must end with semicolon
    if not sql.strip().endswith(";"):
        warnings.append("SQL does not end with a semicolon.")

    # 3. Block DDL by default
    ddl_allowed = ALLOW_DDL or allow_ddl_override
    if not ddl_allowed and _contains_blocked_ddl(sql_upper):
        errors.append("DDL statements are blocked by default (DROP/TRUNCATE/ALTER/CREATE/RENAME).")

    # 4. Dangerous patterns
    if _is_destructive_without_where(sql_upper):
        errors.append("UPDATE or DELETE detected without a WHERE clause — refusing to execute.")

    # Skip schema/column checks for body-DDL statements (procedures, functions,
    # triggers, events) — the body references tables that are valid at runtime
    # but cannot be verified statically against the current schema snapshot.
    if _is_body_ddl(sql_upper):
        valid = len(errors) == 0
        return {"valid": valid, "errors": errors, "warnings": warnings}

    # 5. Schema check — warn on unknown table names
    known_tables = set(t.lower() for t in schema.keys())
    allowed_external_schemas = {"information_schema", "mysql", "performance_schema", "sys"}
    mentioned_tables = _extract_table_names(sql_upper)
    for t in mentioned_tables:
        if t not in known_tables and t not in allowed_external_schemas:
            errors.append(f"Table '{t}' does not exist in the schema.")

    # 6. Schema check — catch unknown alias.column references early.
    alias_map = _extract_alias_table_map(primary_sql)
    unknown_cols = _find_unknown_columns(primary_sql, alias_map, schema)
    for alias, column, table in unknown_cols:
        errors.append(f"Column '{alias}.{column}' does not exist in table '{table}'.")

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors, "warnings": warnings}


def _is_destructive_without_where(sql_upper: str) -> bool:
    is_update_or_delete = sql_upper.startswith("UPDATE") or sql_upper.startswith("DELETE")
    has_where = "WHERE" in sql_upper
    return is_update_or_delete and not has_where


def _contains_blocked_ddl(sql_upper: str) -> bool:
    return bool(re.search(r"\b(DROP|TRUNCATE|ALTER|CREATE|RENAME)\b", sql_upper))


def _is_body_ddl(sql_upper: str) -> bool:
    """Return True for CREATE/ALTER statements that contain a BEGIN...END body
    (procedures, functions, triggers, events). These cannot be schema-checked
    statically because table references live inside the routine body."""
    return bool(re.search(
        r"\b(CREATE|ALTER)\s+(DEFINER\s*=\s*\S+\s+)?(PROCEDURE|FUNCTION|TRIGGER|EVENT)\b",
        sql_upper
    ))


def _extract_table_names(sql_upper: str) -> list[str]:
    """
    Naive extraction: look for words after FROM, JOIN, INTO, UPDATE that match known tables.
    This avoids false positives on arbitrary SQL keywords.
    """
    import re
    # Find words after FROM, JOIN variants, INTO, UPDATE
    pattern = r"(?:FROM|JOIN|INTO|UPDATE)\s+([`\"]?(\w+)[`\"]?)"
    matches = re.findall(pattern, sql_upper)
    found = [m[1].lower() for m in matches]
    # Only return tables we think should exist (filter out subquery aliases etc.)
    # We check all found names against known tables — unknowns become errors
    return found


def _extract_alias_table_map(sql: str) -> dict[str, str]:
    """Map SQL aliases to concrete table names for FROM/JOIN clauses."""
    pattern = r"(?:FROM|JOIN)\s+[`\"]?(\w+)[`\"]?(?:\s+(?:AS\s+)?[`\"]?(\w+)[`\"]?)?"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)

    alias_map: dict[str, str] = {}
    for table, alias in matches:
        table_lower = table.lower()
        alias_map[table_lower] = table_lower
        if alias:
            alias_map[alias.lower()] = table_lower
    return alias_map


def _find_unknown_columns(sql: str, alias_map: dict[str, str], schema: dict) -> list[tuple[str, str, str]]:
    """Return invalid alias.column references based on known schema columns."""
    pattern = r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)"
    refs = re.findall(pattern, sql)
    if not refs:
        return []

    schema_cols = {
        table.lower(): {col.get("name", "").lower() for col in info.get("columns", [])}
        for table, info in schema.items()
    }

    unknown: list[tuple[str, str, str]] = []
    for alias, column in refs:
        alias_lower = alias.lower()
        column_lower = column.lower()

        table = alias_map.get(alias_lower)
        if not table:
            continue

        valid_cols = schema_cols.get(table, set())
        if valid_cols and column_lower not in valid_cols:
            unknown.append((alias, column, table))

    # De-duplicate while preserving order.
    deduped: list[tuple[str, str, str]] = []
    seen = set()
    for item in unknown:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped