"""
Explanation Module — generates plain-English summaries of the final SQL query
and its results for end-user readability.
"""
from llm_client import chat

EXPLAINER_SYSTEM_PROMPT = """You are a helpful database assistant that explains SQL query results in plain English.

Given the original user request, the SQL that was executed, and a summary of the results,
write a short, clear explanation of what was done and what the results mean.

Rules:
- Write 1-3 sentences maximum.
- Focus on what the query retrieved or changed, and what the results mean for the user.
- If rows were returned, highlight the key finding (count, notable values, pattern).
- If rows were affected (INSERT/UPDATE/DELETE), describe what changed.
- Use plain, non-technical language — avoid SQL terms like SELECT, WHERE, JOIN.
- Do not restate or quote the SQL.
- Be specific with numbers when they are available.
"""


def explain_result(
    user_request: str,
    sql: str,
    rows: list,
    affected_rows: int,
    operation_type: str,
) -> str:
    """
    Generate a plain-English explanation of a query result.

    Args:
        user_request: The original natural language request from the user.
        sql: The SQL that was executed.
        rows: Result rows returned by the database (may be empty for write ops).
        affected_rows: Number of rows inserted/updated/deleted.
        operation_type: Broad operation category ("read", "write", "schema", etc.).

    Returns:
        A 1-3 sentence plain-English explanation string.
        Falls back to a generic message if the LLM call fails.
    """
    result_summary = _build_result_summary(rows, affected_rows, operation_type)

    user_message = f"""User request: {user_request}

SQL executed:
{sql}

Result: {result_summary}

Write a plain-English explanation:"""

    try:
        return chat(EXPLAINER_SYSTEM_PROMPT, user_message, temperature=0.3)
    except Exception:
        return _fallback_explanation(operation_type, rows, affected_rows)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_result_summary(rows: list, affected_rows: int, operation_type: str) -> str:
    if rows:
        row_count = len(rows)
        # Include a small sample so the LLM can describe actual values
        sample = rows[:5]
        return f"{row_count} row(s) returned. Sample data: {sample}"
    if affected_rows > 0:
        return f"{affected_rows} row(s) affected by the {operation_type} operation."
    return "Query executed successfully with no rows returned or affected."


def _fallback_explanation(operation_type: str, rows: list, affected_rows: int) -> str:
    if rows:
        return f"The query returned {len(rows)} record(s)."
    if affected_rows > 0:
        return f"The operation completed successfully, affecting {affected_rows} row(s)."
    return "The query executed successfully."
