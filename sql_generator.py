import re
import config
from llm_client import chat
from schema_retriever import schema_to_prompt_text

SYSTEM_PROMPT = """You are an expert MySQL query writer.
You will be given a database schema and a user's request in plain English.
Your job is to write a single, valid MySQL query that satisfies the request.

Rules:
- Output ONLY the raw SQL query — no explanation, no markdown, no backticks.
- Use only the tables and columns that exist in the schema provided.
- Always use table aliases for clarity in joins.
- Never use SELECT * — always name the columns.
- For plain read/list requests without an explicit row count, default to LIMIT 10.
- If the user explicitly asks for all/full/every row or says no limit, do not add LIMIT.
- For DELETE or UPDATE, always include a WHERE clause.
- Output must be a single complete SQL statement ending with a semicolon.
- Do not assume hidden business intent. If the request is ambiguous (for example, "top 5 customers"),
  return a direct list query with LIMIT using the most relevant table, instead of inventing a metric.
"""


def generate_sql(user_request: str, schema: dict) -> str:
    """
    Generate a SQL query from a natural language request.

    Args:
        user_request: Plain English description of what to query.
        schema: Dict from schema_retriever.get_schema().

    Returns:
        Raw SQL string.
    """
    deterministic_sql = _build_schema_intent_sql(user_request)
    if deterministic_sql:
        return deterministic_sql

    deterministic_sql = _build_simple_top_n_sql(user_request, schema)
    if deterministic_sql:
        return deterministic_sql

    deterministic_sql = _build_simple_table_scan_sql(user_request, schema)
    if deterministic_sql:
        return deterministic_sql

    deterministic_sql = _build_common_analytics_sql(user_request, schema)
    if deterministic_sql:
        return deterministic_sql

    schema_text = schema_to_prompt_text(schema)
    user_message = f"""Database schema:
{schema_text}

User request:
{user_request}

Write the MySQL query:"""

    raw = chat(SYSTEM_PROMPT, user_message)
    return _clean_sql(raw)


def _build_simple_top_n_sql(user_request: str, schema: dict) -> str | None:
    """
    Handle plain requests like "top 5 customers" deterministically.
    This avoids model over-interpretation on small/fast LLMs.
    """
    request = user_request.strip().lower().rstrip("?.!")

    # If user already specifies semantics, let the LLM handle it.
    semantic_keywords = (" by ", " where ", " group ", " having ", " order ", " with ")
    if any(k in f" {request} " for k in semantic_keywords):
        return None

    match = re.match(r"^(?:show|list|get|fetch|give me\s+)?top\s+(\d+)\s+([a-zA-Z_][\w\s]*)$", request)
    if not match:
        return None

    limit = int(match.group(1))
    if limit <= 0:
        return None

    entity = match.group(2).strip()
    table = _resolve_table_name(entity, schema)
    if not table:
        available = ", ".join(sorted(schema.keys())[:12])
        raise ValueError(
            f"Table/entity '{entity}' is not present in the active schema for top-N query. "
            f"Available tables: {available}"
        )

    alias = table[0].lower()
    columns = _pick_columns(schema.get(table, {}).get("columns", []))
    if not columns:
        return None
    selected = ", ".join(f"{alias}.{col}" for col in columns)
    return f"SELECT {selected}\nFROM {table} {alias}\nLIMIT {limit};"


def _build_simple_table_scan_sql(user_request: str, schema: dict) -> str | None:
    """Handle simple prompts like 'show rows from employees sorted in descending order'."""
    request = user_request.strip().lower().rstrip("?.!")
    normalized = " ".join(request.split())

    verb_tokens = ("show", "list", "get", "fetch")
    row_tokens = ("row", "rows", "record", "records")
    if not any(token in normalized for token in verb_tokens):
        return None
    if not any(token in normalized for token in row_tokens):
        return None
    if " from " not in f" {normalized} ":
        return None

    match = re.search(r"\bfrom\s+([a-zA-Z_][\w\s]*)", normalized)
    if not match:
        return None

    raw_entity = match.group(1)
    # Remove trailing intent words after table phrase.
    raw_entity = re.split(r"\b(sorted|order|where|limit|top|by|with)\b", raw_entity)[0].strip()
    if not raw_entity:
        return None

    table = _resolve_table_name(raw_entity, schema)
    if not table:
        available = ", ".join(sorted(schema.keys())[:12])
        raise ValueError(
            f"Table '{raw_entity}' is not present in the active schema for simple table scan. "
            f"Available tables: {available}"
        )

    alias = table[0].lower()
    use_star = config.ALLOW_SELECT_STAR_SIMPLE_READS and _requests_full_result_set(normalized)
    if use_star:
        selected = "*"
    else:
        columns = _pick_columns(schema.get(table, {}).get("columns", []))
        if not columns:
            return None
        selected = ", ".join(f"{alias}.{col}" for col in columns)

    order_clause = ""
    if "descending" in normalized or "desc order" in normalized or "desc" in normalized:
        sort_col = _pick_sort_column(schema.get(table, {}).get("columns", []))
        if sort_col:
            order_clause = f"\nORDER BY {alias}.{sort_col} DESC"
    elif "ascending" in normalized or "asc order" in normalized or "asc" in normalized:
        sort_col = _pick_sort_column(schema.get(table, {}).get("columns", []))
        if sort_col:
            order_clause = f"\nORDER BY {alias}.{sort_col} ASC"

    limit_clause = ""
    requested_limit = _extract_requested_limit(normalized)
    if requested_limit is not None:
        limit_clause = f"\nLIMIT {requested_limit}"
    elif not _requests_full_result_set(normalized):
        # For simple read intents, keep result previews bounded by default.
        limit_clause = "\nLIMIT 10"

    if selected == "*":
        return f"SELECT *\nFROM {table}{order_clause}{limit_clause};"

    return f"SELECT {selected}\nFROM {table} {alias}{order_clause}{limit_clause};"


def _extract_requested_limit(normalized_request: str) -> int | None:
    limit_match = re.search(r"\blimit\s+(\d+)\b", normalized_request)
    if limit_match:
        value = int(limit_match.group(1))
        return value if value > 0 else None

    count_match = re.search(r"\b(?:top|first)\s+(\d+)\b", normalized_request)
    if count_match:
        value = int(count_match.group(1))
        return value if value > 0 else None

    return None


def _requests_full_result_set(normalized_request: str) -> bool:
    full_set_markers = (
        " all rows",
        " all records",
        " every row",
        " every record",
        " complete data",
        " full data",
        " no limit",
        " without limit",
    )
    padded = f" {normalized_request} "
    return any(marker in padded for marker in full_set_markers)


def _build_schema_intent_sql(user_request: str) -> str | None:
    """Handle requests that clearly ask for schema/table listing."""
    request = user_request.strip().lower().rstrip("?.!")
    normalized = " ".join(request.split())

    if "tables and row count" in normalized or "tables and row counts" in normalized:
        return (
            "SELECT t.TABLE_NAME, t.TABLE_ROWS\n"
            "FROM INFORMATION_SCHEMA.TABLES t\n"
            "WHERE t.TABLE_SCHEMA = DATABASE()\n"
            "  AND t.TABLE_TYPE = 'BASE TABLE'\n"
            "ORDER BY t.TABLE_NAME;"
        )

    if "row count for each table" in normalized or "count rows in each table" in normalized:
        return (
            "SELECT t.TABLE_NAME, t.TABLE_ROWS\n"
            "FROM INFORMATION_SCHEMA.TABLES t\n"
            "WHERE t.TABLE_SCHEMA = DATABASE()\n"
            "  AND t.TABLE_TYPE = 'BASE TABLE'\n"
            "ORDER BY t.TABLE_NAME;"
        )

    direct_patterns = {
        "show tables",
        "show all tables",
        "list tables",
        "list all tables",
        "what tables",
        "what are the tables",
    }
    if normalized in direct_patterns:
        return "SHOW TABLES;"

    if "table" in normalized and ("show" in normalized or "list" in normalized):
        return "SHOW TABLES;"

    return None


def _resolve_table_name(entity: str, schema: dict) -> str | None:
    table_names = list(schema.keys())
    lookup = {name.lower(): name for name in table_names}

    cleaned = entity.replace(" ", "_")
    candidates = {
        cleaned,
        cleaned.rstrip("s"),
        f"{cleaned}s",
        cleaned[:-1] + "ies" if cleaned.endswith("y") else cleaned,
        cleaned[:-3] + "y" if cleaned.endswith("ies") else cleaned,
    }

    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]

    return None


def _build_common_analytics_sql(user_request: str, schema: dict) -> str | None:
    """Deterministic coverage for frequent analytics-style prompts."""
    request = user_request.strip().lower().rstrip("?.!")
    normalized = " ".join(request.split())

    if "duplicate" in normalized and "email" in normalized:
        table, email_col = _find_table_with_column(schema, ("email", "email_id", "mail"))
        if table and email_col:
            return (
                f"SELECT t.{email_col}, COUNT(*) AS duplicate_count\n"
                f"FROM {table} t\n"
                f"WHERE t.{email_col} IS NOT NULL\n"
                f"GROUP BY t.{email_col}\n"
                "HAVING COUNT(*) > 1\n"
                "ORDER BY duplicate_count DESC;"
            )

    if "most recently created" in normalized or "recently created" in normalized:
        table, sort_col = _find_recent_sort_target(schema)
        if table and sort_col:
            return f"SELECT *\nFROM {table}\nORDER BY {sort_col} DESC\nLIMIT 10;"

    artist_exhibition_sql = _build_artist_exhibition_listing_sql(normalized, schema)
    if artist_exhibition_sql:
        return artist_exhibition_sql

    count_by_match = re.match(r"^count\s+([a-zA-Z_][\w\s]*)\s+by\s+([a-zA-Z_][\w\s]*)$", normalized)
    if count_by_match:
        entity = count_by_match.group(1).strip()
        group_entity = count_by_match.group(2).strip()
        table = _resolve_table_name(entity, schema)
        if not table:
            available = ", ".join(sorted(schema.keys())[:12])
            raise ValueError(
                f"Table/entity '{entity}' is not present in the active schema for count-by query. "
                f"Available tables: {available}"
            )
        if table:
            group_col = _resolve_column_name(group_entity, schema.get(table, {}).get("columns", []))
            if group_col:
                alias = table[0].lower()
                return (
                    f"SELECT {alias}.{group_col}, COUNT(*) AS total_count\n"
                    f"FROM {table} {alias}\n"
                    f"GROUP BY {alias}.{group_col}\n"
                    "ORDER BY total_count DESC;"
                )
            available_cols = ", ".join(
                col.get("name", "") for col in schema.get(table, {}).get("columns", []) if col.get("name")
            )
            raise ValueError(
                f"Column/entity '{group_entity}' is not present in table '{table}' for count-by query. "
                f"Available columns: {available_cols}"
            )

    return None


def _find_table_with_column(schema: dict, preferred_cols: tuple[str, ...]) -> tuple[str | None, str | None]:
    preferred = tuple(col.lower() for col in preferred_cols)
    for table, info in schema.items():
        for col in info.get("columns", []):
            name = (col.get("name") or "").lower()
            if name in preferred:
                return table, col.get("name")
    return None, None


def _find_recent_sort_target(schema: dict) -> tuple[str | None, str | None]:
    recency_priority = (
        "created_at",
        "created_on",
        "updated_at",
        "registration_date",
        "date",
    )
    for table, info in schema.items():
        col_names = [col.get("name") for col in info.get("columns", []) if col.get("name")]
        for preferred in recency_priority:
            for col_name in col_names:
                if col_name.lower() == preferred:
                    return table, col_name

    # Fallback to first table with a primary key column for deterministic ordering.
    for table, info in schema.items():
        for col in info.get("columns", []):
            if col.get("key") == "PRI" and col.get("name"):
                return table, col.get("name")
    return None, None


def _resolve_column_name(entity: str, columns: list[dict]) -> str | None:
    normalized = entity.replace(" ", "_").lower()
    lookup = {str(col.get("name", "")).lower(): col.get("name") for col in columns if col.get("name")}
    if normalized in lookup:
        return lookup[normalized]

    candidates = {
        normalized,
        normalized.rstrip("s"),
        f"{normalized}s",
        normalized[:-1] + "ies" if normalized.endswith("y") else normalized,
        normalized[:-3] + "y" if normalized.endswith("ies") else normalized,
    }
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def _build_artist_exhibition_listing_sql(normalized_request: str, schema: dict) -> str | None:
    if "artist" not in normalized_request or "exhibition" not in normalized_request:
        return None

    bridge_table = _resolve_table_name("artist_exhibition", schema)
    if not bridge_table:
        return None

    artist_table = (
        _resolve_table_name("artist_profile", schema)
        or _resolve_table_name("artists", schema)
        or _resolve_table_name("artist", schema)
    )
    exhibition_table = (
        _resolve_table_name("exhibition", schema)
        or _resolve_table_name("exhibitions", schema)
    )
    if not artist_table or not exhibition_table:
        return None

    bridge_cols = schema.get(bridge_table, {}).get("columns", [])
    artist_cols = schema.get(artist_table, {}).get("columns", [])
    exhibition_cols = schema.get(exhibition_table, {}).get("columns", [])

    bridge_artist_fk = _resolve_column_name("artist_id", bridge_cols)
    bridge_exhibition_fk = _resolve_column_name("exhibition_id", bridge_cols)
    artist_pk = _resolve_column_name("artist_id", artist_cols) or _resolve_column_name("id", artist_cols)
    exhibition_pk = _resolve_column_name("exhibition_id", exhibition_cols) or _resolve_column_name("id", exhibition_cols)

    first_name = _resolve_column_name("first_name", artist_cols)
    last_name = _resolve_column_name("last_name", artist_cols)
    artist_name = _resolve_column_name("name", artist_cols)
    exhibition_name = (
        _resolve_column_name("exhibition_name", exhibition_cols)
        or _resolve_column_name("name", exhibition_cols)
        or _resolve_column_name("title", exhibition_cols)
    )

    if not all([bridge_artist_fk, bridge_exhibition_fk, artist_pk, exhibition_pk, exhibition_name]):
        return None

    if first_name and last_name:
        artist_select = f"CONCAT(a.{first_name}, ' ', a.{last_name}) AS artist_name"
        artist_order = "artist_name"
    elif artist_name:
        artist_select = f"a.{artist_name} AS artist_name"
        artist_order = "artist_name"
    else:
        artist_select = f"a.{artist_pk} AS artist_id"
        artist_order = "artist_id"

    return (
        f"SELECT {artist_select}, e.{exhibition_name} AS exhibition_name\n"
        f"FROM {bridge_table} b\n"
        f"JOIN {artist_table} a ON b.{bridge_artist_fk} = a.{artist_pk}\n"
        f"JOIN {exhibition_table} e ON b.{bridge_exhibition_fk} = e.{exhibition_pk}\n"
        f"ORDER BY exhibition_name, {artist_order}\n"
        "LIMIT 100;"
    )


def _pick_columns(columns: list[dict]) -> list[str]:
    if not columns:
        return []

    key_cols = [col["name"] for col in columns if col.get("key") == "PRI"]
    remaining = [col["name"] for col in columns if col.get("name") not in key_cols]
    chosen = (key_cols + remaining)[:5]
    return chosen


def _pick_sort_column(columns: list[dict]) -> str | None:
    if not columns:
        return None

    # Prefer PK for stable sorting.
    for col in columns:
        if col.get("key") == "PRI":
            return col.get("name")

    return columns[0].get("name")


def _clean_sql(raw: str) -> str:
    """Strip markdown fences and extra whitespace from LLM output."""
    # Remove ```sql ... ``` or ``` ... ```
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```", "")
    cleaned = raw.strip()
    if cleaned and not cleaned.endswith(";"):
        cleaned += ";"
    return cleaned