from datetime import datetime
from pathlib import Path

from database import get_connection
import config


BACKUP_DIR = Path("logs") / "preflight_backups"


def create_preflight_backup(targets: list[str], sql: str) -> str:
    """Create a lightweight preflight backup artifact for critical operations."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = BACKUP_DIR / f"preflight_{stamp}.sql"

    lines = [
        f"-- Preflight backup for DB: {config.DB_NAME}",
        f"-- Generated at UTC: {datetime.utcnow().isoformat()}Z",
        "-- Requested SQL:",
        sql,
        "",
    ]

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        for target in targets:
            try:
                cursor.execute(f"SHOW CREATE TABLE `{target}`")
                row = cursor.fetchone()
                if row and "Create Table" in row:
                    lines.append(f"-- Definition for table {target}")
                    lines.append(row["Create Table"] + ";")
                    lines.append("")
                    continue
            except Exception:
                pass  # Not a table — fall through and try as a view

            try:
                cursor.execute(f"SHOW CREATE VIEW `{target}`")
                row = cursor.fetchone()
                if row and "Create View" in row:
                    lines.append(f"-- Definition for view {target}")
                    lines.append(row["Create View"] + ";")
                    lines.append("")
            except Exception:
                lines.append(f"-- Could not capture definition for target: {target}")
                lines.append("")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    file_path.write_text("\n".join(lines), encoding="utf-8")
    return str(file_path)
