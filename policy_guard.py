from dataclasses import dataclass


ROLE_LEVELS = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


@dataclass
class PolicyDecision:
    allowed: bool
    message: str = ""


def authorize_request(
    role: str,
    operation_type: str,
    risk_level: str,
    execute: bool,
    confirmed: bool,
) -> PolicyDecision:
    """Role-based authorization for query execution behavior."""
    normalized = (role or "viewer").strip().lower()
    if normalized not in ROLE_LEVELS:
        return PolicyDecision(False, f"Unknown APP_ROLE '{role}'. Use viewer, operator, or admin.")

    if not execute:
        return PolicyDecision(True, "")

    if normalized == "viewer" and operation_type != "read":
        return PolicyDecision(False, "Viewer role can only execute read operations.")

    if normalized == "operator" and risk_level in {"high", "critical"}:
        return PolicyDecision(False, "Operator role cannot execute high/critical risk operations.")

    if risk_level in {"high", "critical"} and not confirmed:
        return PolicyDecision(False, "High-risk operation requires confirmation.")

    return PolicyDecision(True, "")
