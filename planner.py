"""
Planner Module — decomposes the user's natural language request into
structured, actionable sub-tasks for downstream modules.
"""
import json
import re

from llm_client import chat
from schema_retriever import schema_to_prompt_text

PLANNER_SYSTEM_PROMPT = """You are a database query planning assistant.

Given a user's natural language database request and the database schema,
decompose the request into a structured plan for a SQL generation pipeline.

Return ONLY a valid JSON object with these exact fields:
{
  "intent": "read|write|delete|update|insert|schema|analytics",
  "target_entities": ["list of tables or entities referenced"],
  "filters": ["list of filter conditions mentioned, or empty"],
  "aggregations": ["list of aggregations needed e.g. count sum avg, or empty"],
  "joins_needed": true or false,
  "sort_criteria": "sort description or null",
  "limit": integer or null,
  "sub_tasks": ["step 1", "step 2"],
  "risk_assessment": "low|medium|high|critical",
  "notes": "any special considerations or empty string"
}

Rules:
- Output ONLY the JSON object — no explanation, no markdown, no backticks.
- sub_tasks should be 2-5 plain English steps describing how to fulfill the request.
- risk_assessment: "critical" for DROP/TRUNCATE, "high" for DELETE/UPDATE without
  a clear WHERE, "medium" for INSERT/CREATE, "low" for SELECT/SHOW.
"""


def plan_request(user_request: str, schema: dict) -> dict:
    """
    Decompose a natural language request into a structured plan.

    Args:
        user_request: Plain English query from the user.
        schema: Full schema dict from schema_retriever.get_schema().

    Returns:
        Dict with keys: intent, target_entities, filters, aggregations,
        joins_needed, sort_criteria, limit, sub_tasks, risk_assessment, notes.
        Falls back to a safe minimal plan if the LLM call fails.
    """
    fast_plan = _try_fast_plan(user_request)
    if fast_plan:
        return fast_plan

    schema_text = schema_to_prompt_text(schema)
    user_message = f"""Database schema:
{schema_text}

User request:
{user_request}

Create the structured plan:"""

    try:
        raw = chat(PLANNER_SYSTEM_PROMPT, user_message, temperature=0.0)
        raw = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE)
        raw = raw.replace("```", "").strip()
        plan = json.loads(raw)
        return _normalize_plan(plan)
    except Exception:
        return _default_plan(user_request)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _try_fast_plan(user_request: str) -> dict | None:
    """Deterministic fast path for unambiguous common intents."""
    request = user_request.strip().lower()

    if any(kw in request for kw in ("drop table", "drop database", "truncate")):
        return _make_plan(
            intent="schema",
            target_entities=[],
            filters=[],
            aggregations=[],
            joins_needed=False,
            sort_criteria=None,
            limit=None,
            sub_tasks=[
                "Identify target table from request",
                "Generate DROP/TRUNCATE SQL statement",
                "Validate against DDL policy",
                "Require explicit confirmation before execution",
            ],
            risk_assessment="critical",
            notes="Destructive schema operation — requires explicit confirmation.",
        )

    if any(phrase in request for phrase in ("show tables", "list tables", "list all tables", "show all tables")):
        return _make_plan(
            intent="schema",
            target_entities=["INFORMATION_SCHEMA.TABLES"],
            filters=[],
            aggregations=[],
            joins_needed=False,
            sort_criteria=None,
            limit=None,
            sub_tasks=[
                "Query INFORMATION_SCHEMA for current database table list",
                "Return table names to user",
            ],
            risk_assessment="low",
            notes="",
        )

    return None


def _normalize_plan(plan: dict) -> dict:
    defaults = {
        "intent": "read",
        "target_entities": [],
        "filters": [],
        "aggregations": [],
        "joins_needed": False,
        "sort_criteria": None,
        "limit": None,
        "sub_tasks": [],
        "risk_assessment": "low",
        "notes": "",
    }
    for key, default in defaults.items():
        plan.setdefault(key, default)
    return plan


def _default_plan(user_request: str) -> dict:
    """Fallback plan used when LLM is unavailable or returns unparseable output."""
    request = user_request.strip().lower()
    if any(kw in request for kw in ("delete", "drop", "truncate")):
        risk = "high"
        intent = "delete"
    elif any(kw in request for kw in ("update",)):
        risk = "medium"
        intent = "update"
    elif any(kw in request for kw in ("insert", "create", "add")):
        risk = "medium"
        intent = "insert"
    else:
        risk = "low"
        intent = "read"

    return _make_plan(
        intent=intent,
        target_entities=[],
        filters=[],
        aggregations=[],
        joins_needed=False,
        sort_criteria=None,
        limit=None,
        sub_tasks=[
            "Retrieve live database schema",
            "Generate SQL from natural language request",
            "Validate SQL for safety and schema compliance",
            "Execute query and return results",
        ],
        risk_assessment=risk,
        notes="Plan generated via fallback (LLM unavailable or parse error).",
    )


def _make_plan(
    intent: str,
    target_entities: list,
    filters: list,
    aggregations: list,
    joins_needed: bool,
    sort_criteria,
    limit,
    sub_tasks: list,
    risk_assessment: str,
    notes: str,
) -> dict:
    return {
        "intent": intent,
        "target_entities": target_entities,
        "filters": filters,
        "aggregations": aggregations,
        "joins_needed": joins_needed,
        "sort_criteria": sort_criteria,
        "limit": limit,
        "sub_tasks": sub_tasks,
        "risk_assessment": risk_assessment,
        "notes": notes,
    }
