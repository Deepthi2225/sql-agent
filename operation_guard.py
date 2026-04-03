import re


READ_OPS = {"SELECT", "SHOW", "DESCRIBE", "EXPLAIN"}
WRITE_OPS = {"INSERT", "UPDATE", "DELETE", "REPLACE"}
SCHEMA_OPS = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"}
SECURITY_OPS = {"GRANT", "REVOKE"}
TRANSACTION_OPS = {"COMMIT", "ROLLBACK", "START", "BEGIN", "SAVEPOINT"}
RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def classify_sql(sql: str) -> dict:
    """Classify SQL into operation and risk metadata for policy checks."""
    first = _first_keyword(sql)

    if first in READ_OPS:
        operation_type = "read"
        risk_level = "low"
    elif first in WRITE_OPS:
        operation_type = "write"
        risk_level = "medium"
    elif first in SCHEMA_OPS:
        operation_type = "schema"
        risk_level = "critical"
    elif first in SECURITY_OPS:
        operation_type = "security"
        risk_level = "critical"
    elif first in TRANSACTION_OPS:
        operation_type = "transaction"
        risk_level = "medium"
    elif first in {"CALL"}:
        operation_type = "routine"
        risk_level = "high"
    else:
        operation_type = "unknown"
        risk_level = "high"

    requires_confirmation = risk_level in {"high", "critical"}
    return {
        "operation_type": operation_type,
        "risk_level": risk_level,
        "requires_confirmation": requires_confirmation,
    }


def build_execution_plan(sql: str) -> dict:
    """Build a lightweight execution plan summary for dry-run preview."""
    first = _first_keyword(sql)
    targets = _extract_targets(sql)
    classification = classify_sql(sql)
    return {
        "summary": f"{first} operation on {', '.join(targets) if targets else 'unknown target'}",
        "statement_count": _count_statements(sql),
        "targets": targets,
        "operation_type": classification["operation_type"],
        "risk_level": classification["risk_level"],
    }


def classify_intent(user_request: str) -> dict:
    """Classify prompt intent risk regardless of generated SQL drift."""
    text = user_request.lower()

    critical_markers = [
        "drop ", "truncate ", "alter ", "create database", "drop database",
        "grant ", "revoke ", "trigger", "stored procedure", "function",
    ]
    high_markers = ["create table", "create index", "rename table", "procedure", "event"]
    medium_markers = ["delete ", "update ", "insert "]

    if any(marker in text for marker in critical_markers):
        return {"risk_level": "critical", "requires_confirmation": True}
    if any(marker in text for marker in high_markers):
        return {"risk_level": "high", "requires_confirmation": True}
    if any(marker in text for marker in medium_markers):
        return {"risk_level": "medium", "requires_confirmation": False}
    return {"risk_level": "low", "requires_confirmation": False}


def max_risk_level(first: str, second: str) -> str:
    return first if RISK_ORDER.get(first, 0) >= RISK_ORDER.get(second, 0) else second


def _first_keyword(sql: str) -> str:
    if not sql:
        return "UNKNOWN"
    match = re.search(r"\b([A-Za-z]+)\b", sql.strip())
    if not match:
        return "UNKNOWN"
    return match.group(1).upper()


def _extract_targets(sql: str) -> list[str]:
    pattern = r"(?:FROM|JOIN|INTO|UPDATE|TABLE|DATABASE|PROCEDURE|FUNCTION|TRIGGER)\s+[`\"]?([A-Za-z_]\w*)"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)
    seen = set()
    targets = []
    for item in matches:
        low = item.lower()
        if low in seen:
            continue
        seen.add(low)
        targets.append(item)
    return targets


def _count_statements(sql: str) -> int:
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    return len(statements)
