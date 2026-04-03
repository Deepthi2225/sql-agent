# Self-Correcting SQL Agent

Natural-language to SQL pipeline with validation, execution, and retry-based self-correction.

## Features

- Natural language to MySQL SQL generation
- Live schema retrieval from INFORMATION_SCHEMA
- Pre-execution SQL validation (basic safety checks)
- Auto-correction loop when SQL fails
- Streamlit UI for interactive usage
- React + CSS web UI for a modern frontend experience
- FastAPI backend endpoints for the React UI
- Optional FastAPI route generation from successful SQL

## Project Structure

- app.py: Streamlit UI entry point
- web_api.py: FastAPI backend for React UI
- controller.py: Orchestration pipeline
- database.py: MySQL connection and query execution
- schema_retriever.py: Schema introspection and prompt formatting
- sql_generator.py: Initial SQL generation via LLM
- validator.py: Safety and structure checks
- self_corrector.py: SQL correction loop prompt
- api_generator.py: FastAPI route generation
- frontend/: React + CSS client (Vite)
- Sample_db.sql: Sample ecommerce schema + seed data

## Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Copy env template and fill credentials.

```powershell
Copy-Item .env.example .env
```

4. Load sample database (optional, recommended).

```powershell
mysql -u root -p < Sample_db.sql
```

Set DB_NAME=shop_db in .env if using the sample DB.

## Run React UI (Recommended)

1. Start backend API:

```powershell
uvicorn web_api:app --reload
```

2. In a new terminal, start the React frontend:

```powershell
cd frontend
npm install
npm run dev
```

3. Open the local Vite URL (usually http://127.0.0.1:5173).

## Run Streamlit UI (Optional)

```powershell
streamlit run app.py
```

## Run Generated API

After downloading or creating generated_api.py, run:

```powershell
uvicorn api_runner:app --reload
```

Then verify health:

```powershell
curl http://127.0.0.1:8000/api/health
```

## Run Tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Notes

- For LLM_PROVIDER=ollama, run Ollama locally and ensure the selected model is available.
- For groq/openai, add valid API keys in .env.
- The validator blocks UPDATE/DELETE without WHERE.
- DDL statements are blocked by default. Set ALLOW_DDL=true only for trusted workflows.
- Multi-statement SQL is blocked by default. Set ALLOW_MULTI_STATEMENTS=true to enable.
- By default, simple full-row prompts can use `SELECT *` (for example, "show all rows from auditlog"). Set ALLOW_SELECT_STAR_SIMPLE_READS=false to force explicit column lists.
- Query API now supports `dry_run` preview mode and `confirm_high_risk` for gated execution.
- Audit events are written to `logs/audit_log.jsonl`.

## Query API Safety Controls

POST `/api/query` request body supports:

- `request` (str): Natural-language prompt.
- `generate_api` (bool): Generate FastAPI route from successful SQL.
- `dry_run` (bool): If true, return SQL + execution plan without running it.
- `confirm_high_risk` (bool): Required for high-risk operations.

Response includes:

- `operation_type`: `read|write|schema|security|transaction|routine|unknown`
- `risk_level`: `low|medium|high|critical`
- `requires_confirmation`: Whether explicit confirmation is needed.
- `execution_plan`: Preview summary with target objects.
- `backup_path`: Preflight backup artifact path for confirmed high-risk operations.

## Role-Based Policy

Set `APP_ROLE` in `.env`:

- `viewer`: execute read-only queries; can dry-run anything.
- `operator`: execute low/medium-risk queries; cannot execute high/critical.
- `admin`: can execute all query classes (high/critical require confirmation).

## Additional API Endpoints

- `GET /api/capabilities`: feature and role metadata.
- `GET /api/audit?limit=100`: recent audit events from `logs/audit_log.jsonl`.

## High-Risk Execution Workflow

1. Submit with `dry_run=true` to preview SQL and execution plan.
2. Review risk metadata and targets.
3. Re-submit with `confirm_high_risk=true` to execute.
4. For high/critical operations, a preflight backup artifact is generated in `logs/preflight_backups/`.

## Quick Validation Checklist

- MySQL is running and reachable.
- DB credentials in .env are correct.
- LLM provider is reachable (Ollama running, or API key set).
- Streamlit UI shows Database and LLM status as connected.
