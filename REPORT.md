# Self-Correcting SQL Agent
## Project Report — Semester 6, Large Language Models

---

## 1. Introduction

The **Self-Correcting SQL Agent** is a full-stack AI application that bridges the gap between natural language and relational databases. It allows any user — technical or non-technical — to interact with a MySQL database simply by typing a question in plain English.

The system does not just wrap an LLM around a database. It builds a complete, safety-conscious pipeline around the LLM, treating the language model as one component within a larger system that validates, corrects, classifies, authorizes, executes, and explains every query.

This project was built as part of the Semester 6 LLM course to demonstrate practical, production-oriented LLM engineering — not just API calls to a model, but a complete system with real-world safeguards.

---

## 2. What This Project Is About

At its core, the project answers one question:

> *"How do you safely let a language model talk to a live database?"*

The answer involves several layers:

- **Natural Language Understanding** — an LLM converts the user's question into SQL
- **Deterministic Fast-Paths** — common patterns (top-N, duplicates, counts) bypass the LLM entirely for speed and reliability
- **Pre-Execution Validation** — every generated query is checked for syntax errors, schema mismatches, and dangerous patterns before it touches the database
- **Self-Correction** — if execution fails, the error is fed back to the LLM automatically for up to 3 correction attempts
- **Risk Classification** — every SQL operation is classified by type and risk level, and checked against the user's role before execution
- **Auditability** — every action is logged in a structured audit trail
- **API Generation** — validated queries and database tables can be automatically converted into working FastAPI endpoints

The project is a complete working system — not a demo or a prototype — with a React frontend, FastAPI backend, Streamlit alternative UI, test suite, and sample database.

---

## 3. Expected Outcomes

| Outcome | Description |
|---------|-------------|
| Natural language querying | Users can query any database table using plain English with no SQL knowledge |
| Safe execution | All queries pass validation and authorization before execution |
| Self-healing queries | Failed SQL is automatically corrected without user intervention |
| Advanced DB operations | Stored procedures, triggers, functions, views, and indexes can be created via natural language |
| Auto-generated APIs | Any SQL query or database table can be turned into a REST API endpoint |
| Audit trail | All operations — including failures and corrections — are logged |
| Multi-database support | Switch between databases at runtime without restarting |
| Role-based control | Different users get different levels of access (viewer / operator / admin) |
| Explainable results | Query results are summarized in plain English |

---

## 4. Tech Stack

### Backend

| Technology | Version | Role |
|-----------|---------|------|
| Python | 3.x | Core language |
| FastAPI | 0.111.0 | REST API server |
| Uvicorn | 0.29.0 | ASGI server |
| mysql-connector-python | 8.3.0 | MySQL driver |
| sqlparse | 0.5.0 | SQL syntax parsing and validation |
| python-dotenv | 1.0.1 | Environment configuration |
| requests | 2.31.0 | HTTP client for LLM APIs |
| Streamlit | 1.35.0 | Alternative interactive UI |

### Frontend

| Technology | Version | Role |
|-----------|---------|------|
| React | 18.3.1 | UI framework |
| Vite | 5.4.10 | Build tool and dev server |
| Vanilla CSS | — | Styling |

### LLM Providers (switchable via `.env`)

| Provider | Cost | Model Used |
|----------|------|-----------|
| Groq | Free | llama-3.3-70b-versatile |
| Ollama | Free (local) | Any local model (e.g. llama3, mistral) |
| OpenAI | Paid | gpt-4o-mini or any GPT model |

### Database

- **MySQL** — all queries execute against a live MySQL instance
- Schema introspection via `INFORMATION_SCHEMA` (no hardcoded schema)

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interfaces                       │
│        React + Vite SPA         Streamlit App           │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP / REST
┌───────────────────────▼─────────────────────────────────┐
│               FastAPI Backend  (web_api.py)              │
│  /api/query  /api/schema  /api/audit  /api/generate-crud │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│             Controller  (controller.py)                  │
│         Orchestrates the full NL → SQL pipeline          │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┘
   │          │          │          │          │
Schema    Planner    SQL Gen    Validator  Self-Corrector
   │          │          │          │          │
   └──────────┴──────────┼──────────┴──────────┘
                         │
          ┌──────────────▼──────────────┐
          │  Operation Guard            │
          │  Policy Guard               │
          │  Audit Logger               │
          │  Backup Manager             │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │        MySQL Database        │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  Explainer + API Generator   │
          └─────────────────────────────┘
```

---

## 6. How the Project Was Implemented

### 6.1 Module Breakdown

| Module | Lines | Responsibility |
|--------|-------|----------------|
| `controller.py` | 534 | Orchestrates the entire pipeline end-to-end |
| `sql_generator.py` | 457 | NL → SQL (deterministic patterns + LLM fallback) |
| `api_generator.py` | 473 | Single route generation (LLM) + full CRUD (deterministic) |
| `validator.py` | 163 | SQL safety and schema validation |
| `planner.py` | 196 | Request decomposition into structured plans |
| `database.py` | 190 | MySQL connection, query execution, DELIMITER handling |
| `schema_retriever.py` | 136 | Live schema introspection via INFORMATION_SCHEMA |
| `llm_client.py` | 149 | Unified interface for Ollama / Groq / OpenAI |
| `operation_guard.py` | 110 | SQL classification and risk level assignment |
| `policy_guard.py` | 42 | Role-based authorization enforcement |
| `self_corrector.py` | 74 | Error-driven SQL correction prompt |
| `explainer.py` | 80 | Plain-English result summarization |
| `audit_logger.py` | 47 | JSONL event logging |
| `backup_manager.py` | 60 | Pre-execution backup for high-risk operations |
| `web_api.py` | 205 | FastAPI REST endpoints |
| `app.py` | 183 | Streamlit UI |

### 6.2 Pipeline — Step by Step

Every query follows this path:

```
1. User types natural language request
2. Live schema is fetched from MySQL INFORMATION_SCHEMA
3. Request is decomposed into a structured plan
4. CRUD API shortcut check (if user asked for "generate CRUD for X")
5. SQL generation:
     → Deterministic fast-path if pattern matches
     → LLM-based generation otherwise
6. DELIMITER directives stripped (MySQL CLI-only, incompatible with connector)
7. SQL classified by operation type + risk level
8. Intent-SQL alignment check (prevent correction drift)
9. Pre-execution validation:
     → Syntax check (sqlparse)
     → Schema consistency (table + column existence)
     → Dangerous patterns (UPDATE/DELETE without WHERE)
     → DDL blocking (configurable)
10. Authorization: role vs. risk level check
11. High-risk gate: requires explicit confirmation
12. Preflight backup (for high/critical operations)
13. Execution against MySQL
     → Success → explain results → optionally generate API
     → Failure → self-correction loop (up to 3 attempts)
14. Audit log written
15. Response returned with SQL, results, risk metadata, explanation
```

### 6.3 Self-Correction Loop

When a query fails execution, the system automatically:
1. Captures the exact MySQL error message
2. Constructs a correction prompt with the original request, failed SQL, and error
3. Sends to the LLM to generate a corrected query
4. Re-validates and re-executes the corrected query
5. Repeats up to `MAX_CORRECTION_ATTEMPTS` (default: 3)

This means the user almost never sees a raw error — the system heals itself.

### 6.4 SQL Validation Details

Before any query executes, `validator.py` checks:
- **Syntax**: sqlparse tokenizes and validates structure
- **Schema references**: every table and column mentioned must exist in the live schema
- **Dangerous patterns**: UPDATE/DELETE without WHERE clause are rejected
- **DDL operations**: CREATE/ALTER/DROP/TRUNCATE blocked by default (enabled via `ALLOW_DDL=true`)
- **Multi-statement**: semicolon-separated compound statements blocked by default
- **Body DDL detection**: procedure/function/trigger bodies skip schema checks (table references are runtime-resolved, not static)

### 6.5 API Generation

Two modes are supported:

**Mode 1 — Single Route from SQL (LLM-based)**
When `Generate API` is enabled, the validated SQL is sent to the LLM with a strict prompt template that enforces:
- Synchronous `def` (not `async def`)
- `cursor(dictionary=True)` for dict results not tuples
- Empty result handling (404 response)
- Parameterized queries with `%s`
- Clean `finally` block to close connections

**Mode 2 — Full CRUD from Table (Deterministic)**
For any table, the system generates a complete FastAPI router with:
- `GET /table` — list all (with limit/offset)
- `GET /table/{id}` — get by primary key
- `POST /table` — create new record
- `PUT /table/{id}` — partial update
- `DELETE /table/{id}` — delete by primary key

Files are saved to `generated/apis/<table>.py` and dynamically mounted.

### 6.6 Frontend Features

The React UI has three tabs in the main workspace:

**Ask the Database**
- Natural language input with Ctrl+Enter shortcut
- Toggles: Dry Run, Generate API, Confirm High-Risk
- Example queries, schema explorer, query history
- Results: metrics bar, query plan, generated SQL, result table, explanation

**Workbench**
- All executed SQL queries accumulated in a shared editable textarea
- Queries separated by blank lines, multi-line preserved
- Copy all / Clear all

**Generated APIs**
- All generated FastAPI routes collected per session
- Each shows the original request, timestamp, full code, copy and delete buttons
- Auto-switches to this tab when a new API is generated

---

## 7. Use Cases

### 7.1 Business Analyst / Non-Technical User
A business analyst can query the database without writing SQL:
- *"Show total revenue per product category this year"*
- *"Which customers haven't placed an order in 3 months?"*
- *"List top 10 products by units sold"*

### 7.2 Database Developer
A developer can use it to quickly prototype database objects:
- *"Create a stored procedure that takes a customer_id and returns all their orders"*
- *"Create a trigger that reduces stock when an order item is inserted"*
- *"Create a view showing customer order summary"*

### 7.3 Backend Developer
A developer can auto-generate REST API endpoints:
- *"Create an API for top 10 products by revenue"*
- *"Generate CRUD APIs for the customers table"*
- The generated code is clean, documented, and production-ready

### 7.4 DBA / Admin
An admin can use it to inspect and manage the database safely:
- Role-based access ensures viewers can't run destructive queries
- Audit log tracks every operation
- Preflight backups protect against accidental data loss
- Dry-run mode previews SQL without executing

### 7.5 Education / Learning
Students can use it to learn SQL:
- Type a question, see the generated SQL
- Modify the SQL in the Workbench
- Understand query plans and risk levels

---

## 8. Safety Design

The project treats safety as a first-class concern across 7 layers:

| Layer | Mechanism | What It Prevents |
|-------|-----------|-----------------|
| 1 | SQL syntax validation | Malformed queries crashing the database |
| 2 | Schema reference check | Queries on non-existent tables/columns |
| 3 | Dangerous pattern detection | Accidental bulk deletes/updates |
| 4 | DDL blocking | Schema changes by unauthorized users |
| 5 | Risk classification + RBAC | Wrong role executing high-risk operations |
| 6 | Preflight backups | Data loss before destructive operations |
| 7 | Audit logging | Untracked or unaccountable operations |

All SQL uses parameterized queries (`%s`) via mysql-connector, preventing SQL injection from user input.

---

## 9. Project Structure

```
sql_agent/
├── controller.py          # Pipeline orchestration
├── web_api.py             # FastAPI endpoints
├── app.py                 # Streamlit UI
├── sql_generator.py       # NL → SQL
├── llm_client.py          # LLM abstraction
├── schema_retriever.py    # Schema introspection
├── validator.py           # Pre-execution validation
├── operation_guard.py     # Risk classification
├── policy_guard.py        # RBAC
├── self_corrector.py      # Error correction
├── planner.py             # Request planning
├── explainer.py           # Result explanation
├── api_generator.py       # API code generation
├── api_runner.py          # Generated API loader
├── audit_logger.py        # Event logging
├── backup_manager.py      # Preflight backups
├── database.py            # MySQL connection
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
├── .env                   # Active configuration
├── Sample_db.sql          # Demo database
├── frontend/              # React + Vite UI
│   └── src/
│       ├── App.jsx
│       └── styles.css
├── generated/apis/        # Auto-generated CRUD APIs
├── logs/                  # Audit log + backups
└── tests/                 # Unit and integration tests
```

---

## 10. Sample Database

The included `Sample_db.sql` contains a realistic e-commerce schema:

| Table | Rows | Description |
|-------|------|-------------|
| `categories` | 5 | Product categories |
| `customers` | 10 | Customer profiles with city/country |
| `products` | 15 | Catalog with pricing and stock |
| `orders` | 15 | Orders with status (pending/shipped/delivered/etc.) |
| `order_items` | 24 | Line items linking orders to products |
| `reviews` | 15 | 1–5 star ratings with comments |

**Foreign key relationships:**
- `orders.customer_id → customers.id`
- `order_items.order_id → orders.id`
- `order_items.product_id → products.id`
- `reviews.product_id → products.id`
- `reviews.customer_id → customers.id`
- `products.category_id → categories.id`

---

## 11. How to Run the Project

### Prerequisites
- Python 3.10+
- Node.js 18+
- MySQL server running locally
- A free Groq API key from [console.groq.com](https://console.groq.com) (or Ollama installed locally)

### Step 1 — Clone and Install

```bash
# Install Python dependencies
cd sql_agent
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Step 2 — Configure Environment

Edit `.env` with your credentials:

```env
# LLM Provider
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# MySQL
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=shop_db

# Settings
MAX_CORRECTION_ATTEMPTS=3
APP_ROLE=admin
ALLOW_DDL=true
ALLOW_MULTI_STATEMENTS=true
```

### Step 3 — Load Sample Database

```bash
mysql -u root -p < Sample_db.sql
```

### Step 4 — Start the Backend

```bash
python -m uvicorn web_api:app --reload --port 8000
```

### Step 5 — Start the Frontend

```bash
cd frontend
npm run dev
```

### Step 6 — Open the App

Open **http://localhost:5173** in your browser.

---

### Alternative: Streamlit UI

If you prefer a simpler single-page UI without running the React frontend:

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

---

## 12. API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Backend, DB, and LLM connectivity status |
| `/api/schema` | GET | Live database schema |
| `/api/databases` | GET | List available MySQL databases |
| `/api/database/select` | POST | Switch active database |
| `/api/examples` | GET | Suggested example queries |
| `/api/capabilities` | GET | Enabled features and current role |
| `/api/query` | POST | Execute a natural language query |
| `/api/audit` | GET | Recent audit log entries |
| `/api/generate-crud` | POST | Generate full CRUD API for a table |
| `/api/generated-apis` | GET | List all generated CRUD files |

---

## 13. Example Prompts

### Basic Reads
```
Show all tables and row counts
List the 10 most recently created customers
Find duplicate email addresses in the customers table
Show the top 5 products by price
```

### Aggregations and Joins
```
Show total revenue per product category
List top 5 customers by total amount spent
Show average order value per month
Which products have never been ordered
```

### Write Operations
```
Insert a new customer with first name John, last name Doe, email john@example.com
Update the stock of product id 1 to 50
Delete all orders with status cancelled
```

### Stored Procedures
```
Create a stored procedure called get_customer_orders that takes a customer_id and returns all their orders
Call the stored procedure get_customer_orders with customer id 1
```

### Triggers and Functions
```
Create a trigger that reduces stock when a new row is inserted into order_items
Create a function called get_full_name that takes first_name and last_name and returns them joined
```

### Views and Indexes
```
Create a view called customer_order_summary showing each customer full name, total orders, and total amount spent
Create an index on the email column of the customers table
```

### API Generation
```
Create an API for top 10 products by revenue
Generate CRUD APIs for the customers table
```

---

## 14. Completeness Summary

| Feature | Status |
|---------|--------|
| Natural language to SQL | Complete |
| Deterministic fast-paths | Complete |
| Live schema introspection | Complete |
| Pre-execution validation | Complete |
| Self-correction loop | Complete |
| Risk classification | Complete |
| Role-based access control | Complete |
| DDL support (procedures, triggers, functions, views, indexes) | Complete |
| DELIMITER stripping for MySQL connector | Complete |
| Preflight backups | Complete |
| Audit logging | Complete |
| Query planning | Complete |
| Result explanation | Complete |
| Multi-provider LLM (Ollama / Groq / OpenAI) | Complete |
| React + Vite frontend | Complete |
| Streamlit alternative UI | Complete |
| FastAPI REST backend | Complete |
| Workbench (editable SQL history) | Complete |
| Generated APIs tab | Complete |
| CRUD API auto-generation | Complete |
| Dynamic API loader | Complete |
| Sample e-commerce database | Complete |
| Unit and integration tests | Complete |

---

*Built for Semester 6 — Large Language Models course.*
*Stack: Python · FastAPI · React · MySQL · Groq (llama-3.3-70b-versatile)*
