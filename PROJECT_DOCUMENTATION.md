# Self-Correcting SQL Agent — Project Documentation

**Course:** Semester 6 — Large Language Models (LLM)
**Project Type:** Applied LLM Engineering
**Date:** March 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Core Features](#5-core-features)
6. [Module Breakdown](#6-module-breakdown)
7. [Pipeline Flow](#7-pipeline-flow)
8. [User Interfaces](#8-user-interfaces)
9. [Safety & Security Design](#9-safety--security-design)
10. [API Generation Feature](#10-api-generation-feature)
11. [Testing & Quality](#11-testing--quality)
12. [Configuration & Setup](#12-configuration--setup)
13. [Sample Database](#13-sample-database)
14. [Project Completeness Assessment](#14-project-completeness-assessment)

---

## 1. Project Overview

The **Self-Correcting SQL Agent** is a full-stack AI application that converts natural language questions into validated, executable MySQL queries. It uses a Large Language Model (LLM) as its reasoning engine, wrapped with a robust pipeline that ensures safety, correctness, and auditability.

A user can type a question like *"Show me the top 5 customers by total order value"* and the system will:
1. Parse the intent
2. Inspect the live database schema
3. Generate the appropriate SQL query
4. Validate and classify the query for safety and risk
5. Execute it (with automatic error correction if needed)
6. Return the results with a plain-English explanation
7. Optionally generate a reusable REST API endpoint for that query

---

## 2. Problem Statement

Writing SQL queries requires knowledge of both the database schema and SQL syntax, creating a barrier for non-technical users. Existing solutions either:
- Require strict templates (not flexible enough)
- Send raw LLM output directly to the database (unsafe)
- Provide no auditability or access control

This project solves the problem by building a **multi-stage pipeline** that combines LLM flexibility with deterministic safety checks, making natural language database access both practical and safe.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interfaces                         │
│         React + Vite SPA          Streamlit Web App             │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────────────────┐
│                    FastAPI Backend (web_api.py)                  │
│   /api/query  /api/schema  /api/audit  /api/generate-crud  ...  │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  Controller (controller.py)                      │
│          Orchestrates the entire NL → SQL pipeline               │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
Schema    Planner    SQL        Validator  Self-
Retriever           Generator             Corrector
   │          │          │          │          │
   └──────────┴──────────┼──────────┴──────────┘
                         │
         ┌───────────────▼───────────────┐
         │  Operation Guard + Policy      │
         │  Guard + Audit Logger          │
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │       MySQL Database           │
         └───────────────────────────────┘
                         │
         ┌───────────────▼───────────────┐
         │  Explainer + API Generator     │
         └───────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate validation from generation | LLMs can produce invalid SQL; a deterministic validator catches these errors before execution |
| Self-correction loop | Instead of failing silently, the system feeds database error messages back to the LLM for automatic correction |
| Multi-provider LLM abstraction | Supports Ollama (free, local), Groq (free cloud), and OpenAI so the system works without paid API keys |
| Deterministic fast-paths | Common patterns (top-N, duplicates, table listing) bypass the LLM entirely for speed and reliability |
| Role-based access control | SQL operations are classified by risk level and checked against the user's role before execution |

---

## 4. Technology Stack

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.x | Core language |
| FastAPI | 0.111.0 | REST API backend |
| Uvicorn | 0.29.0 | ASGI server |
| Streamlit | 1.35.0 | Alternative interactive UI |
| mysql-connector-python | 8.3.0 | MySQL database driver |
| sqlparse | 0.5.0 | SQL parsing and validation |
| python-dotenv | 1.0.1 | Environment configuration |
| requests | 2.31.0 | HTTP client for LLM APIs |

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.3.1 | UI framework |
| Vite | 5.4.10 | Build tool and dev server |
| Vanilla CSS | — | Styling (no external framework) |

### LLM Providers (configurable)
| Provider | Cost | Notes |
|----------|------|-------|
| Ollama | Free | Runs locally; no internet required |
| Groq | Free tier | Cloud API, fast inference |
| OpenAI | Paid | GPT models via official API |

### Database
- **MySQL** — all queries are generated and executed against a live MySQL instance
- Schema introspection via `INFORMATION_SCHEMA`

---

## 5. Core Features

### 5.1 Natural Language to SQL
Users type plain English questions. The system converts them to valid MySQL queries using one of two paths:
- **Deterministic fast-path:** Regex-based matching for common patterns (top-N queries, duplicate detection, table scans, counts)
- **LLM-based generation:** Sends the schema context + user question to an LLM for query generation

### 5.2 Live Schema Introspection
The system reads the actual database schema at runtime using `INFORMATION_SCHEMA`. It never relies on hardcoded table definitions — this means it works with any database automatically.

### 5.3 Self-Correction Loop
If a generated SQL query fails during execution, the system:
1. Captures the exact database error message
2. Sends it back to the LLM along with the original query and error
3. Requests a corrected query
4. Retries (up to 3 times by default)

This dramatically reduces the failure rate without user intervention.

### 5.4 Multi-Layer SQL Validation
Before execution, every query passes through a validator that checks:
- SQL syntax validity (via sqlparse)
- Table and column existence against the live schema
- Blocked operations (DDL: CREATE/DROP/ALTER/TRUNCATE by default)
- Destructive operation safety (UPDATE/DELETE without WHERE clause)
- Multi-statement execution control

### 5.5 Risk Classification & Authorization
Every query is classified by:
- **Operation type:** read, write, schema, security, transaction, routine
- **Risk level:** low, medium, high, critical

Execution is then checked against the user's configured role:
- `viewer` — read-only access
- `operator` — reads + safe writes
- `admin` — full access including schema changes

High/critical operations can require explicit confirmation before execution.

### 5.6 Preflight Backups
Before executing high-risk or critical operations (e.g., bulk deletes), the system creates a backup snapshot of the affected data in `logs/preflight_backups/`.

### 5.7 Query Planning
Complex requests are decomposed by the LLM into a structured execution plan identifying:
- Target tables/entities
- Required joins
- Aggregations and groupings
- Sorting and filtering
- Result format

### 5.8 Result Explanation
After successful query execution, the system generates a plain-English summary of the results, making the output accessible to non-technical users.

### 5.9 Audit Logging
Every action is logged to `logs/audit_log.jsonl` in JSON Lines format, including:
- Timestamps
- User requests
- Generated SQL
- Execution outcomes
- Corrections made
- Risk classifications

### 5.10 CRUD API Generation
For any database table, the system can auto-generate a complete FastAPI CRUD API with endpoints for list, get-by-id, create, update, and delete. Generated files are saved to `generated/apis/` and dynamically loaded at runtime.

---

## 6. Module Breakdown

| Module | Lines | Responsibility |
|--------|-------|----------------|
| `controller.py` | ~400 | Orchestrates the entire pipeline end-to-end |
| `web_api.py` | 205 | FastAPI REST endpoints for the React frontend |
| `app.py` | 182 | Streamlit UI entry point |
| `sql_generator.py` | ~330 | NL → SQL conversion (deterministic + LLM paths) |
| `llm_client.py` | 149 | Unified interface for Ollama / Groq / OpenAI |
| `schema_retriever.py` | 136 | Live MySQL schema introspection |
| `validator.py` | 146 | SQL safety and correctness validation |
| `operation_guard.py` | 110 | SQL operation type and risk level classification |
| `policy_guard.py` | 42 | Role-based access control enforcement |
| `self_corrector.py` | 74 | Error-driven SQL correction loop |
| `planner.py` | 196 | Request decomposition into execution plans |
| `explainer.py` | 80 | Plain-English result summarization |
| `api_generator.py` | ~380 | FastAPI CRUD route generation from SQL/tables |
| `api_runner.py` | 77 | Dynamic discovery and mounting of generated APIs |
| `audit_logger.py` | 47 | JSONL event logging |
| `backup_manager.py` | 60 | Preflight backup creation |
| `database.py` | 147 | MySQL connection management and query execution |
| `config.py` | 44 | Environment variable loading |

**Total source code:** ~3,185 lines of Python

---

## 7. Pipeline Flow

```
User types natural language question
              │
              ▼
[1] Audit Log: request_received
              │
              ▼
[2] Fetch live schema from MySQL INFORMATION_SCHEMA
              │
              ▼
[3] Plan the request
    ├─ Deterministic: extract intent from pattern matching
    └─ LLM: decompose into structured plan
              │
              ▼
[4] Classify intent risk level (from user's original text)
              │
              ▼
[5] Generate SQL query
    ├─ Deterministic fast-path (SHOW TABLES, TOP N, etc.)
    └─ LLM-based generation with schema context
              │
              ▼
[6] Validate SQL
    ├─ Parse syntax
    ├─ Check table/column references exist
    ├─ Enforce safety rules (no DDL, no unguarded deletes)
    └─ If invalid → return error to user
              │
              ▼
[7] Classify SQL operation type and risk level
              │
              ▼
[8] Check authorization (role vs. risk level)
    └─ If unauthorized → return access denied
              │
              ▼
[9] If high/critical risk → create preflight backup
              │
              ▼
[10] Execute query against MySQL
    ├─ If success → proceed
    └─ If failure → self-correction loop (max 3 attempts)
              │
              ▼
[11] Audit Log: completion event
              │
              ▼
[12] Generate explanation (plain English summary)
              │
              ▼
[13] (Optional) Generate API route if requested
              │
              ▼
Response returned with:
  • Generated SQL
  • Query results
  • Corrections made (if any)
  • Risk metadata
  • Execution plan
  • Natural language explanation
  • Generated API route (if requested)
```

---

## 8. User Interfaces

### 8.1 React + Vite Frontend

A modern Single-Page Application served via Vite (dev) or the built `dist/` folder.

**Key UI features:**
- Health status indicator (backend connectivity)
- Database selector (switch between MySQL databases at runtime)
- Natural language query input with example prompts
- Dry-run toggle (preview SQL without executing)
- Risk badge display (low / medium / high / critical)
- Results table with column headers
- Plain-English result explanation
- SQL editor showing the generated query
- CRUD API generation button per table
- Confirmation dialogs for high-risk operations

**Architecture:** React 18 + Vite 5, communicates with the FastAPI backend via REST.

### 8.2 Streamlit UI

An alternative, single-file interactive web app for quick testing without a separate frontend build.

**Key features:**
- Schema explorer (expandable table/column details)
- Query input with plan visualization
- Session history
- Generated API route preview and download

**Run with:** `streamlit run app.py`

### 8.3 FastAPI REST API

Backend API with the following endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Backend and database health check |
| `/api/query` | POST | Execute a natural language query |
| `/api/schema` | GET | Retrieve the current database schema |
| `/api/audit` | GET | List recent audit log events |
| `/api/databases` | GET | List available MySQL databases |
| `/api/databases/switch` | POST | Switch active database |
| `/api/generate-crud` | POST | Generate CRUD API for a table |
| `/api/capabilities` | GET | Discover enabled feature flags |

---

## 9. Safety & Security Design

The project treats safety as a first-class concern across multiple layers:

### Layer 1 — Input Validation
- All SQL is parsed with sqlparse before execution
- Schema references are verified against live database state
- DDL operations (CREATE, DROP, ALTER, TRUNCATE) are blocked by default

### Layer 2 — Operation Classification
Every SQL statement is classified by `operation_guard.py`:
- Regex-based pattern matching on SQL text
- Risk levels: `low` (SELECT), `medium` (INSERT/UPDATE), `high` (DELETE), `critical` (DROP/TRUNCATE)

### Layer 3 — Role-Based Authorization
`policy_guard.py` enforces access control:
- `viewer` role cannot execute any write operations
- `operator` role can execute safe writes but not schema changes
- `admin` role has full access

### Layer 4 — Destructive Operation Guards
- UPDATE/DELETE without a WHERE clause is rejected
- Multi-statement queries are blocked unless explicitly enabled
- SELECT * is configurable (enabled/disabled via `.env`)

### Layer 5 — Preflight Backups
Before any high-risk or critical operation, the current state of affected data is backed up to `logs/preflight_backups/` as a timestamped JSON file.

### Layer 6 — Audit Trail
All events — including failed attempts, corrections, and access denials — are appended to `logs/audit_log.jsonl` for forensic review.

### Layer 7 — SQL Injection Prevention
All parameterized queries use mysql-connector's parameterized execution (not string interpolation), preventing SQL injection from user input.

---

## 10. API Generation Feature

One of the most distinctive features of this project is automatic REST API generation.

**How it works:**
1. User clicks "Generate CRUD API" for a table (e.g., `customers`)
2. `api_generator.py` introspects the table schema
3. Generates a complete FastAPI router file with 5 endpoints:
   - `GET /customers` — list all records (with optional filters)
   - `GET /customers/{id}` — get one record by primary key
   - `POST /customers` — create a new record
   - `PUT /customers/{id}` — update an existing record
   - `DELETE /customers/{id}` — delete a record
4. Saves the generated file to `generated/apis/<table>.py`
5. `api_runner.py` dynamically discovers and mounts all generated routers at startup

**Example generated files already present:**
- `generated/apis/artists.py`
- `generated/apis/employee.py`

This feature converts any database table into a fully functional REST API with zero manual coding.

---

## 11. Testing & Quality

### Unit Tests (`tests/`)

| Test File | Coverage |
|-----------|----------|
| `test_sql_generator.py` | 20+ tests for NL→SQL conversion, schema queries, top-N, duplicates, joins, aggregations, error cases |
| `test_controller.py` | End-to-end pipeline integration tests |
| `test_validator.py` | SQL validation logic tests |
| `test_policy_guard.py` | Role-based authorization enforcement tests |

### Quality Benchmark (`_quality_benchmark.py`)
An automated integration test suite that runs 12 test cases covering:
- Various SQL patterns and complexity levels
- Risk level verification against expected values
- SQL pattern validation (correct clauses generated)
- Dry-run execution mode
- Success/correction rate metrics

### Sample Database (`Sample_db.sql`)
A realistic e-commerce database schema with 7+ tables:
- `categories`, `customers`, `products`, `orders`, `order_items`, `employees`, `artists`
- 300+ lines including seed data and foreign key relationships
- Designed to test joins, aggregations, and complex queries

---

## 12. Configuration & Setup

### Environment Variables (`.env`)

```env
# LLM Provider
LLM_PROVIDER=ollama           # ollama | groq | openai
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

GROQ_API_KEY=<your-key>
GROQ_MODEL=llama3-8b-8192

OPENAI_API_KEY=<your-key>
OPENAI_MODEL=gpt-3.5-turbo

# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<your-password>
DB_NAME=sample_db

# Safety Flags
MAX_CORRECTION_ATTEMPTS=3
APP_ROLE=operator             # viewer | operator | admin
ALLOW_DDL=false
ALLOW_MULTI_STATEMENTS=false
ALLOW_SELECT_STAR_SIMPLE_READS=true
```

### Running the Project

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Load sample database (optional)
mysql -u root -p < Sample_db.sql

# 3. Configure .env with your credentials

# Option A: FastAPI + React (full stack)
uvicorn web_api:app --reload --port 8000
cd frontend && npm install && npm run dev

# Option B: Streamlit only
streamlit run app.py
```

---

## 13. Sample Database

The included `Sample_db.sql` provides a realistic test environment:

| Table | Description |
|-------|-------------|
| `categories` | Product categories |
| `products` | Product catalog with pricing and stock |
| `customers` | Customer profiles |
| `orders` | Order headers with dates and statuses |
| `order_items` | Line items linking orders to products |
| `employees` | Staff records |
| `artists` | Music artist data (for join query testing) |

These tables allow testing of:
- Simple SELECT queries
- Multi-table JOINs (orders + customers + products)
- Aggregations (total revenue, order counts)
- TOP-N queries (best-selling products, top customers)
- Filtered queries (orders by date range, products by category)

---

## 14. Project Completeness Assessment

### Completed Features

- Natural language to SQL conversion (LLM + deterministic paths)
- Multi-provider LLM support (Ollama, Groq, OpenAI)
- Live MySQL schema introspection
- SQL syntax and schema validation
- Self-correction loop (up to 3 attempts)
- Risk classification (4 levels)
- Role-based access control (3 roles)
- Preflight backup system
- JSONL audit logging
- Query planning and explanation
- Automatic CRUD API generation
- Dynamic API router mounting
- Streamlit interactive UI
- React + Vite modern frontend
- FastAPI REST backend with 8+ endpoints
- Unit and integration test suite
- Quality benchmark script
- Sample database with seed data
- Environment-based configuration
- SQL injection protection

### Summary

This project is a **complete, production-quality implementation** of a self-correcting SQL agent. It demonstrates:

- **LLM integration** — using language models as a reasoning engine within a controlled pipeline
- **Software engineering discipline** — clear module separation, error handling, and testability
- **Security awareness** — multiple defensive layers, audit trails, and role-based access control
- **Full-stack development** — Python backend, React frontend, REST API design
- **Practical AI design** — knowing when NOT to use an LLM (deterministic fast-paths), and how to recover when it fails (self-correction)

The project goes significantly beyond a basic LLM wrapper by treating the language model as one component within a larger, safety-conscious system.
