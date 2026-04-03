import json
import re
from urllib import request

BASE_URL = "http://127.0.0.1:8000/api/query"

TESTS = [
    {"name": "basic_read", "prompt": "show all rows from auditlog", "expect": r"FROM\s+auditlog", "risk": r"low", "dry": True},
    {"name": "limit_read", "prompt": "show rows from employee limit 5", "expect": r"FROM\s+employee", "risk": r"low", "dry": True},
    {"name": "schema_tables", "prompt": "show all tables", "expect": r"SHOW\s+TABLES", "risk": r"low", "dry": True},
    {"name": "schema_row_counts", "prompt": "show all tables and row counts", "expect": r"INFORMATION_SCHEMA\.TABLES", "risk": r"low", "dry": True},
    {"name": "top_n_simple", "prompt": "top 5 employee", "expect": r"FROM\s+employee", "risk": r"low", "dry": True},
    {"name": "duplicate_emails", "prompt": "find duplicate email addresses", "expect": r"(GROUP\s+BY|HAVING|COUNT\()", "risk": r"low", "dry": True},
    {"name": "recent_records", "prompt": "list the 10 most recently created records", "expect": r"(ORDER\s+BY|LIMIT\s+10)", "risk": r"low", "dry": True},
    {"name": "join_like", "prompt": "list artists with their exhibition names", "expect": r"(JOIN|FROM\s+artist_|FROM\s+exhibition)", "risk": r"low", "dry": True},
    {"name": "aggregation", "prompt": "count employees by role", "expect": r"(GROUP\s+BY|COUNT\()", "risk": r"low", "dry": True},
    {"name": "high_risk_delete", "prompt": "delete all rows from auditlog", "expect": r"DELETE", "risk": r"(high|critical)", "dry": True},
    {"name": "ddl_drop", "prompt": "drop table auditlog", "expect": r"DROP\s+TABLE", "risk": r"(high|critical)", "dry": True},
    {"name": "update_guarded", "prompt": "update employee set salary=0", "expect": r"UPDATE\s+employee", "risk": r"(high|critical)", "dry": True},
]


def call_query(prompt: str, dry_run: bool) -> dict:
    payload = json.dumps({"request": prompt, "dry_run": dry_run, "generate_api": False}).encode("utf-8")
    req = request.Request(BASE_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    results = []

    for test in TESTS:
        try:
            response = call_query(test["prompt"], test["dry"])
            sql = (response.get("sql") or "")
            results.append(
                {
                    "case": test["name"],
                    "success": bool(response.get("success")),
                    "risk": response.get("risk_level"),
                    "risk_ok": bool(re.search(test["risk"], str(response.get("risk_level") or ""), flags=re.IGNORECASE)),
                    "sql_ok": bool(re.search(test["expect"], sql, flags=re.IGNORECASE)),
                    "corrections": int(response.get("correction_attempts") or 0),
                    "error": response.get("error") or "",
                    "sql": sql.replace("\n", " "),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "case": test["name"],
                    "success": False,
                    "risk": "n/a",
                    "risk_ok": False,
                    "sql_ok": False,
                    "corrections": 0,
                    "error": str(exc),
                    "sql": "",
                }
            )

    total = len(results)
    summary = {
        "total": total,
        "success_count": sum(1 for item in results if item["success"]),
        "sql_match_count": sum(1 for item in results if item["sql_ok"]),
        "risk_match_count": sum(1 for item in results if item["risk_ok"]),
        "avg_corrections": round(sum(item["corrections"] for item in results) / total, 2) if total else 0.0,
    }

    print("===SUMMARY===")
    print(json.dumps(summary, indent=2))
    print("===DETAILS===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
