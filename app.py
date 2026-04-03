"""
Streamlit UI for the Self-Correcting LLM SQL Agent
Run with:  streamlit run app.py
"""
import streamlit as st
import pandas as pd

from database import test_connection
from llm_client import is_llm_available, get_provider_label
from schema_retriever import get_schema
from controller import run_query
from api_generator import generate_full_api_file

st.set_page_config(
    page_title="SQL Agent",
    page_icon="🤖",
    layout="wide",
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Self-Correcting SQL Agent")
st.caption("Natural language → validated SQL → (optional) FastAPI routes, powered by Ollama llama3")

# ── Sidebar: status checks ────────────────────────────────────────────────────
with st.sidebar:
    st.header("System Status")

    db_ok  = test_connection()
    llm_ok = is_llm_available()

    st.markdown(f"**Database:** {'🟢 Connected' if db_ok else '🔴 Not connected'}")
    st.markdown(f"**LLM:** {'🟢 Ready' if llm_ok else '🔴 Not ready'}")
    st.caption(f"Provider: {get_provider_label()}")

    if not db_ok:
        st.error("Check your .env DB settings and ensure MySQL is running.")
    if not llm_ok:
        from config import LLM_PROVIDER
        if LLM_PROVIDER == "ollama":
            st.warning("Run `ollama serve` in a terminal to start Ollama.")
        elif LLM_PROVIDER == "groq":
            st.warning("Set GROQ_API_KEY in .env — free at console.groq.com")
        elif LLM_PROVIDER == "openai":
            st.warning("Set OPENAI_API_KEY in .env")

    st.divider()

    st.header("Schema Explorer")
    if db_ok:
        if st.button("Refresh schema"):
            st.session_state.pop("schema", None)

        if "schema" not in st.session_state:
            with st.spinner("Loading schema..."):
                try:
                    st.session_state["schema"] = get_schema()
                except Exception as e:
                    st.error(f"Schema error: {e}")
                    st.session_state["schema"] = {}

        schema = st.session_state.get("schema", {})
        for table, info in schema.items():
            with st.expander(f"📋 {table}"):
                for col in info["columns"]:
                    flags = []
                    if col["key"] == "PRI":
                        flags.append("PK")
                    if not col["nullable"]:
                        flags.append("NOT NULL")
                    flag_str = f"  `{'`, `'.join(flags)}`" if flags else ""
                    st.markdown(f"- **{col['name']}** `{col['type']}`{flag_str}")

    st.divider()
    st.header("Session History")
    if "history" not in st.session_state:
        st.session_state["history"] = []
    if st.session_state["history"]:
        for i, h in enumerate(reversed(st.session_state["history"][-5:])):
            st.markdown(f"`{i+1}.` {h['request'][:50]}...")
    else:
        st.caption("No queries yet.")

# ── Main: query input ─────────────────────────────────────────────────────────
st.subheader("Ask a question about your database")

col1, col2 = st.columns([4, 1])
with col1:
    user_request = st.text_area(
        "Your request",
        placeholder="e.g.  Show me the top 5 customers by total order value",
        height=100,
        label_visibility="collapsed",
    )
with col2:
    generate_api = st.checkbox("Generate API route", value=False)
    run_btn = st.button("Run", type="primary", use_container_width=True, disabled=not (db_ok and llm_ok))

# ── Example queries ───────────────────────────────────────────────────────────
st.caption("Examples:")
example_cols = st.columns(3)
examples = [
    "Show all tables and row counts",
    "Find duplicate email addresses",
    "List the 10 most recently created records",
]
for i, ex in enumerate(examples):
    if example_cols[i].button(ex, use_container_width=True):
        user_request = ex
        run_btn = True

# ── Run pipeline ──────────────────────────────────────────────────────────────
if run_btn and user_request.strip():
    with st.spinner("Thinking..."):
        result = run_query(user_request.strip(), generate_api=generate_api)

    # Save to history
    st.session_state["history"].append({
        "request": user_request,
        "success": result.success,
        "sql": result.sql,
    })

    # ── Results ───────────────────────────────────────────
    st.divider()

    meta_cols = st.columns(4)
    meta_cols[0].metric("Status", "✅ Success" if result.success else "❌ Failed")
    meta_cols[1].metric("Corrections", result.correction_attempts)
    meta_cols[2].metric("Rows", result.affected_rows)
    meta_cols[3].metric("Time", f"{result.duration_ms:.0f} ms")

    if result.validation_warnings:
        for w in result.validation_warnings:
            st.warning(f"Validator: {w}")

    if result.sql:
        with st.expander("Generated SQL", expanded=True):
            st.code(result.sql, language="sql")

    if result.plan and result.plan.get("sub_tasks"):
        with st.expander("Query Plan", expanded=False):
            st.markdown(f"**Intent:** `{result.plan.get('intent', 'unknown')}`")
            if result.plan.get("target_entities"):
                st.markdown(f"**Target tables:** {', '.join(result.plan['target_entities'])}")
            if result.plan.get("joins_needed"):
                st.markdown("**Joins required:** Yes")
            if result.plan.get("risk_assessment"):
                st.markdown(f"**Risk assessment:** `{result.plan['risk_assessment']}`")
            st.markdown("**Steps:**")
            for i, step in enumerate(result.plan["sub_tasks"], 1):
                st.markdown(f"{i}. {step}")
            if result.plan.get("notes"):
                st.info(result.plan["notes"])

    if not result.success:
        st.error(result.error)
    else:
        if result.explanation:
            st.info(result.explanation)
        if result.rows:
            st.subheader("Results")
            df = pd.DataFrame(result.rows)
            st.dataframe(df, use_container_width=True)
        else:
            st.success(f"Query executed successfully. {result.affected_rows} row(s) affected.")

    if generate_api and result.api_route:
        with st.expander("Generated FastAPI Route", expanded=False):
            st.code(result.api_route, language="python")

        # Offer to download as a full API file
        full_file = generate_full_api_file([
            {"request": user_request, "sql": result.sql, "route_code": result.api_route}
        ])
        st.download_button(
            "Download API file",
            data=full_file,
            file_name="generated_api.py",
            mime="text/x-python",
        )

elif run_btn and not user_request.strip():
    st.warning("Please enter a request first.")