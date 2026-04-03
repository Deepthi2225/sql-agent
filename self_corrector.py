from llm_client import chat
from schema_retriever import schema_to_prompt_text

CORRECTION_SYSTEM_PROMPT = """You are an expert MySQL debugger.
You will be given:
1. A database schema
2. The original user request
3. A SQL query that failed
4. The exact error message from MySQL

Your job is to fix the SQL query so it executes successfully.

Rules:
- Output ONLY the corrected raw SQL — no explanation, no markdown, no backticks.
- Use only tables and columns that exist in the provided schema.
- Fix the root cause of the error, not just the symptom.
- The query must end with a semicolon.
- Preserve the original user intent exactly; do not switch to unrelated tables or domains.
- Prefer the simplest valid query that satisfies the request.
- Keep the SQL operation family aligned with intent:
    - drop/truncate/alter/create intent -> schema operation only (no silent rewrite to DELETE/UPDATE)
    - delete intent -> DELETE
    - update intent -> UPDATE
    - insert intent -> INSERT/REPLACE
- If a direct intent-faithful SQL cannot be produced under constraints, return the closest intent-faithful SQL
    that will fail safely, rather than changing to a different operation.
"""


def correct_sql(
    original_request: str,
    failed_sql: str,
    error_message: str,
    schema: dict,
    attempt: int,
) -> str:
    """
    Ask the LLM to fix a SQL query given the execution error.

    Args:
        original_request: What the user originally asked for.
        failed_sql: The SQL that failed.
        error_message: The MySQL error string.
        schema: Full schema dict.
        attempt: Which correction attempt this is (for logging).

    Returns:
        Corrected SQL string.
    """
    import re

    schema_text = schema_to_prompt_text(schema)
    user_message = f"""Database schema:
{schema_text}

Original user request:
{original_request}

SQL that failed (attempt {attempt}):
{failed_sql}

MySQL error:
{error_message}

Write the corrected MySQL query:"""

    raw = chat(CORRECTION_SYSTEM_PROMPT, user_message)

    # Strip markdown fences
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```", "").strip()
    if raw and not raw.endswith(";"):
        raw += ";"
    return raw