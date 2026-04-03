import json
from datetime import datetime
from pathlib import Path


AUDIT_PATH = Path("logs") / "audit_log.jsonl"


def log_audit_event(event_type: str, payload: dict) -> None:
    """Append an audit event as JSONL. Never break app flow on logging failures."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "payload": payload,
        }
        with AUDIT_PATH.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(event, ensure_ascii=True) + "\n")
    except Exception:
        # Audit logging must be best-effort and should not fail requests.
        return


def read_recent_audit_events(limit: int = 100) -> list[dict]:
    """Read most recent audit events from JSONL file."""
    if limit <= 0:
        return []
    if not AUDIT_PATH.exists():
        return []

    try:
        lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    events = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events
