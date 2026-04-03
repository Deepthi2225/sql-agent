"""
Controller — orchestrates the full pipeline:
  User request → Schema → Generate SQL → Validate → Execute
      → [Self-correct on error] → Explain → (Optional) Generate API
"""
import re
import time
from dataclasses import dataclass, field

from config import ALLOW_DDL, APP_ROLE, MAX_CORRECTION_ATTEMPTS
from audit_logger import log_audit_event
from backup_manager import create_preflight_backup
from operation_guard import build_execution_plan, classify_intent, classify_sql, max_risk_level
from policy_guard import authorize_request
from schema_retriever import get_schema
from sql_generator import generate_sql
from validator import validate_sql
from database import execute_query, _strip_delimiter
from self_corrector import correct_sql
from api_generator import generate_api_route, generate_crud_api, detect_crud_table
from planner import plan_request
from explainer import explain_result


@dataclass
class QueryResult:
    success: bool
    sql: str = ""
    rows: list = field(default_factory=list)
    affected_rows: int = 0
    error: str = ""
    correction_attempts: int = 0
    validation_warnings: list = field(default_factory=list)
    api_route: str = ""
    duration_ms: float = 0.0
    operation_type: str = "unknown"
    risk_level: str = "high"
    requires_confirmation: bool = True
    execution_plan: dict = field(default_factory=dict)
    intent_risk_level: str = "low"
    backup_path: str = ""
    plan: dict = field(default_factory=dict)
    explanation: str = ""
    generated_file: str = ""


def run_query(
    user_request: str,
    generate_api: bool = False,
    execute: bool = True,
    confirmed: bool = False,
) -> QueryResult:
    """
    Full pipeline entry point.

    Args:
        user_request: Natural language query from the user.
        generate_api: If True, also generate a FastAPI route.

    Returns:
        QueryResult with all output fields populated.
    """
    start = time.time()
    result = QueryResult(success=False)
    log_audit_event("request_received", {
        "user_request": user_request,
        "generate_api": generate_api,
        "execute": execute,
        "confirmed": confirmed,
    })
    intent_policy = classify_intent(user_request)
    result.intent_risk_level = intent_policy["risk_level"]

    # ── 1. Fetch live schema ──────────────────────────────
    try:
        schema = get_schema()
    except Exception as e:
        result.error = f"Schema retrieval failed: {e}"
        result.duration_ms = (time.time() - start) * 1000
        log_audit_event("schema_failed", {"error": result.error})
        return result

    # ── 1b. Plan the request ──────────────────────────────
    try:
        result.plan = plan_request(user_request, schema)
        log_audit_event("request_planned", {"plan": result.plan})
    except Exception as e:
        # Planner failure is non-fatal — pipeline continues without a plan
        result.plan = {}
        result.validation_warnings.append(f"Query planner unavailable: {e}")
        log_audit_event("planner_failed", {"error": str(e)})

    # ── 1c. CRUD API generation short-circuit ────────────────────────
    crud_table = detect_crud_table(user_request, schema)
    if crud_table:
        try:
            code, filepath = generate_crud_api(crud_table, schema)
            result.success = True
            result.sql = f"-- CRUD API generated for table: {crud_table}"
            result.api_route = code
            result.generated_file = filepath
            result.operation_type = "api_generation"
            result.risk_level = "low"
            result.requires_confirmation = False
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("crud_api_generated", {
                "table": crud_table,
                "filepath": filepath,
            })
            return result
        except Exception as exc:
            result.error = f"CRUD generation failed: {exc}"
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("crud_api_failed", {"table": crud_table, "error": str(exc)})
            return result

    requested_table = _extract_requested_table(user_request)
    if requested_table:
        resolved_table = _resolve_table_name(requested_table, schema)
        if not resolved_table:
            available = ", ".join(sorted(schema.keys())[:12])
            result.error = (
                f"Table '{requested_table}' was requested but does not exist in the active database. "
                f"Available tables: {available}"
            )
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("intent_table_not_found", {
                "requested_table": requested_table,
                "available_tables": sorted(schema.keys())[:12],
            })
            return result

    # ── 2. Generate initial SQL ───────────────────────────
    try:
        sql = generate_sql(user_request, schema)
    except Exception as e:
        result.error = f"SQL generation failed: {e}"
        result.duration_ms = (time.time() - start) * 1000
        log_audit_event("generation_failed", {"error": result.error})
        return result

    # Strip DELIMITER directives immediately — they are MySQL CLI-only and
    # must be removed before validation, classification, and execution.
    sql, _ = _strip_delimiter(sql)

    _populate_operation_metadata(result, sql)
    _apply_effective_risk_policy(result, intent_policy)
    log_audit_event("sql_generated", {
        "sql": sql,
        "operation_type": result.operation_type,
        "risk_level": result.risk_level,
        "intent_risk_level": result.intent_risk_level,
    })

    intent_alignment_error = _check_intent_sql_alignment(user_request, sql)
    if intent_alignment_error:
        log_audit_event("intent_sql_mismatch", {
            "user_request": user_request,
            "sql": sql,
            "error": intent_alignment_error,
        })
        sql = _correction_loop(
            user_request,
            sql,
            intent_alignment_error,
            schema,
            result,
            intent_policy,
            confirmed,
            execute,
        )
        if result.success:
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("query_success", {
                "sql": result.sql,
                "correction_attempts": result.correction_attempts,
            })
            return result
        if result.error:
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("query_failed", {
                "error": result.error,
                "sql": result.sql,
            })
            return result

    # ── 3. Pre-execution validation ───────────────────────
    validation = validate_sql(
        sql,
        schema,
        allow_ddl_override=confirmed,
        allow_multi_override=confirmed,
    )
    result.validation_warnings = validation["warnings"]

    if not validation["valid"]:
        if _should_fail_fast_on_validation(validation["errors"], intent_policy, confirmed):
            result.sql = sql
            result.error = validation["errors"][0]
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("validation_failed_fast", {
                "errors": validation["errors"],
                "sql": sql,
            })
            return result

        # Feed validation errors back as if they were execution errors
        error_text = "; ".join(validation["errors"])
        log_audit_event("validation_failed", {"errors": validation["errors"], "sql": sql})
        sql = _correction_loop(
            user_request,
            sql,
            error_text,
            schema,
            result,
            intent_policy,
            confirmed,
            execute,
        )
        if result.success:
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("query_success", {
                "sql": result.sql,
                "correction_attempts": result.correction_attempts,
            })
            return result
        if result.error:
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("query_failed", {
                "error": result.error,
                "sql": result.sql,
            })
            return result

    _populate_operation_metadata(result, sql)
    _apply_effective_risk_policy(result, intent_policy)

    if not execute:
        result.success = True
        result.sql = sql
        result.duration_ms = (time.time() - start) * 1000
        log_audit_event("dry_run_preview", {
            "sql": sql,
            "execution_plan": result.execution_plan,
        })
        return result

    policy = authorize_request(APP_ROLE, result.operation_type, result.risk_level, execute, confirmed)
    if not policy.allowed:
        result.sql = sql
        result.error = policy.message
        result.duration_ms = (time.time() - start) * 1000
        log_audit_event("authorization_denied", {
            "role": APP_ROLE,
            "operation_type": result.operation_type,
            "risk_level": result.risk_level,
            "message": policy.message,
        })
        return result

    if result.requires_confirmation and not confirmed:
        result.sql = sql
        result.error = (
            "High-risk operation requires confirmation. "
            "Resubmit with confirm_high_risk=true to execute."
        )
        result.duration_ms = (time.time() - start) * 1000
        log_audit_event("confirmation_required", {
            "sql": sql,
            "risk_level": result.risk_level,
            "operation_type": result.operation_type,
            "intent_risk_level": result.intent_risk_level,
        })
        return result

    if confirmed and result.risk_level in {"high", "critical"}:
        try:
            targets = result.execution_plan.get("targets", [])
            result.backup_path = create_preflight_backup(targets, sql)
            log_audit_event("preflight_backup_created", {
                "backup_path": result.backup_path,
                "targets": targets,
            })
        except Exception as exc:
            result.sql = sql
            result.error = f"Preflight backup failed: {exc}"
            result.duration_ms = (time.time() - start) * 1000
            log_audit_event("preflight_backup_failed", {"error": str(exc)})
            return result

    # ── 4. Execute ────────────────────────────────────────
    exec_result = execute_query(sql, allow_multi=confirmed)

    if exec_result["success"]:
        result.success = True
        result.sql = sql
        result.rows = exec_result["rows"]
        result.affected_rows = exec_result["affected"]
        log_audit_event("query_success", {
            "sql": sql,
            "affected_rows": result.affected_rows,
            "operation_type": result.operation_type,
        })
        try:
            result.explanation = explain_result(
                user_request, sql, result.rows, result.affected_rows, result.operation_type
            )
        except Exception:
            result.explanation = ""
    else:
        # ── 5. Self-correction loop ───────────────────────
        log_audit_event("execution_failed", {
            "sql": sql,
            "error": exec_result["error"],
        })
        sql = _correction_loop(
            user_request,
            sql,
            exec_result["error"],
            schema,
            result,
            intent_policy,
            confirmed,
            execute,
        )

    # ── 6. API generation (optional) ─────────────────────
    if result.success and generate_api:
        try:
            result.api_route = generate_api_route(user_request, result.sql)
        except Exception as e:
            result.api_route = f"# API generation failed: {e}"

    result.duration_ms = (time.time() - start) * 1000
    if not result.success:
        log_audit_event("query_failed", {
            "sql": result.sql,
            "error": result.error,
            "correction_attempts": result.correction_attempts,
        })
    return result


def _correction_loop(
    user_request: str,
    sql: str,
    error: str,
    schema: dict,
    result: QueryResult,
    intent_policy: dict,
    confirmed: bool,
    execute: bool,
) -> str:
    """Run up to MAX_CORRECTION_ATTEMPTS correction cycles."""
    for attempt in range(1, MAX_CORRECTION_ATTEMPTS + 1):
        result.correction_attempts = attempt
        try:
            sql = correct_sql(user_request, sql, error, schema, attempt)
        except Exception as e:
            result.error = f"Self-correction failed on attempt {attempt}: {e}"
            log_audit_event("correction_failed", {
                "attempt": attempt,
                "error": result.error,
                "sql": sql,
            })
            return sql

        sql, _ = _strip_delimiter(sql)
        log_audit_event("correction_attempt", {
            "attempt": attempt,
            "input_error": error,
            "corrected_sql": sql,
        })

        # Re-validate
        validation = validate_sql(
            sql,
            schema,
            allow_ddl_override=confirmed,
            allow_multi_override=confirmed,
        )
        if not validation["valid"]:
            error = "; ".join(validation["errors"])
            continue

        intent_alignment_error = _check_intent_sql_alignment(user_request, sql)
        if intent_alignment_error:
            error = intent_alignment_error
            continue

        _populate_operation_metadata(result, sql)
        _apply_effective_risk_policy(result, intent_policy)

        policy = authorize_request(APP_ROLE, result.operation_type, result.risk_level, execute, confirmed)
        if not policy.allowed:
            result.success = False
            result.sql = sql
            result.error = policy.message
            return sql

        if result.requires_confirmation and not confirmed:
            result.success = False
            result.sql = sql
            result.error = (
                "High-risk operation requires confirmation. "
                "Resubmit with confirm_high_risk=true to execute."
            )
            return sql

        if not execute:
            result.success = True
            result.sql = sql
            result.rows = []
            result.affected_rows = 0
            return sql

        if confirmed and result.risk_level in {"high", "critical"} and not result.backup_path:
            targets = result.execution_plan.get("targets", [])
            result.backup_path = create_preflight_backup(targets, sql)

        # Re-execute
        exec_result = execute_query(sql, allow_multi=confirmed)
        if exec_result["success"]:
            result.success = True
            result.sql = sql
            result.rows = exec_result["rows"]
            result.affected_rows = exec_result["affected"]
            try:
                result.explanation = explain_result(
                    user_request, sql, result.rows, result.affected_rows, result.operation_type
                )
            except Exception:
                result.explanation = ""
            return sql
        else:
            error = exec_result["error"]

    result.error = (
        f"Could not produce a valid query after {MAX_CORRECTION_ATTEMPTS} attempts. "
        f"Last error: {error}"
    )
    result.sql = sql
    return sql


def _extract_requested_table(user_request: str) -> str | None:
    """Extract table phrase from prompts that explicitly include `from <table>`."""
    normalized = " ".join(user_request.strip().lower().split())
    match = re.search(r"\bfrom\s+([a-zA-Z_][\w\s]*)", normalized)
    if not match:
        return None

    entity = match.group(1)
    entity = re.split(r"\b(sorted|order|where|group|having|limit|top|with|by)\b", entity)[0].strip()
    if not entity:
        return None
    return entity


def _resolve_table_name(entity: str, schema: dict) -> str | None:
    lookup = {name.lower(): name for name in schema.keys()}
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


def _populate_operation_metadata(result: QueryResult, sql: str) -> None:
    classification = classify_sql(sql)
    result.operation_type = classification["operation_type"]
    result.risk_level = classification["risk_level"]
    result.requires_confirmation = classification["requires_confirmation"]
    result.execution_plan = build_execution_plan(sql)


def _apply_effective_risk_policy(result: QueryResult, intent_policy: dict) -> None:
    result.risk_level = max_risk_level(result.risk_level, intent_policy["risk_level"])
    result.requires_confirmation = result.requires_confirmation or intent_policy["requires_confirmation"]


def _check_intent_sql_alignment(user_request: str, sql: str) -> str | None:
    """Ensure corrected SQL does not drift away from the user's operation intent."""
    request = user_request.strip().lower()
    first_keyword = _first_sql_keyword(sql)

    if _contains_any(request, ("drop", "truncate", "alter", "create table", "create database", "rename table")):
        if first_keyword not in {"DROP", "TRUNCATE", "ALTER", "CREATE", "RENAME"}:
            return (
                "Corrected SQL drifted from schema-changing intent. "
                "Keep operation family aligned with requested schema action."
            )

    if _contains_any(request, ("delete",)) and first_keyword != "DELETE":
        return "Corrected SQL must remain a DELETE operation to match the user request."

    if _contains_any(request, ("update",)) and first_keyword != "UPDATE":
        return "Corrected SQL must remain an UPDATE operation to match the user request."

    if _contains_any(request, ("insert",)) and first_keyword not in {"INSERT", "REPLACE"}:
        return "Corrected SQL must remain an INSERT/REPLACE operation to match the user request."

    return None


def _first_sql_keyword(sql: str) -> str:
    match = re.search(r"^\s*([A-Za-z]+)", sql or "")
    return (match.group(1).upper() if match else "")


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _should_fail_fast_on_validation(errors: list[str], intent_policy: dict, confirmed: bool) -> bool:
    if confirmed:
        return False

    if ALLOW_DDL:
        return False

    if intent_policy.get("risk_level") != "critical":
        return False

    return any("DDL statements are blocked" in err for err in errors)