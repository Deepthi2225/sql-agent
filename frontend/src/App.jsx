import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

/* ── tiny helpers ───────────────────────────────────────────────────────── */
function dot(on) {
  return <span className={`dot ${on ? "dot-on" : "dot-off"}`} />;
}

function Badge({ label, kind = "neutral" }) {
  return <span className={`badge badge-${kind}`}>{label}</span>;
}

function Toggle({ checked, onChange, label }) {
  return (
    <label className="toggle-pill">
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="pill" />
      <span className="toggle-label">{label}</span>
    </label>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }
  return (
    <button className="btn-copy" type="button" onClick={handleCopy}>
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

function Spinner() {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      <span>Running query…</span>
    </div>
  );
}

function RiskBadge({ level }) {
  const kind =
    level === "critical" ? "crit"
    : level === "high" ? "warn"
    : level === "medium" ? "med"
    : "ok";
  return <Badge label={level || "—"} kind={kind} />;
}

/* ── workbench card ─────────────────────────────────────────────────────── */

/* ── main app ───────────────────────────────────────────────────────────── */
const initialStatus = {
  status: "unknown",
  database: false,
  database_name: "-",
  llm: false,
  provider: "-",
};

export default function App() {
  const [status, setStatus]               = useState(initialStatus);
  const [schema, setSchema]               = useState({});
  const [examples, setExamples]           = useState([]);
  const [request, setRequest]             = useState("");
  const [generateApi, setGenerateApi]     = useState(false);
  const [dryRun, setDryRun]               = useState(true);
  const [confirmHighRisk, setConfirmHighRisk] = useState(false);
  const [loading, setLoading]             = useState(false);
  const [result, setResult]               = useState(null);
  const [history, setHistory]             = useState([]);
  const [error, setError]                 = useState("");
  const [databases, setDatabases]         = useState([]);
  const [selectedDb, setSelectedDb]       = useState("");
  const [switchingDb, setSwitchingDb]     = useState(false);
  const [planOpen, setPlanOpen]           = useState(false);
  const [workbench, setWorkbench]         = useState([]);
  const [generatedApis, setGeneratedApis] = useState([]); // [{title, code, at}]
  const [activeTab, setActiveTab]         = useState("query"); // "query" | "workbench" | "apis"

  const textareaRef = useRef(null);
  const canRun = status.database && status.llm && request.trim().length > 0 && !loading;

  const rowCount = useMemo(() => {
    if (!result || !Array.isArray(result.rows)) return 0;
    return result.rows.length;
  }, [result]);

  /* ── data fetching ───────────────────────────────────────────────────── */
  const fetchInitialData = useCallback(async () => {
    try {
      const [hRes, sRes, eRes, dRes] = await Promise.all([
        fetch("/api/health"),
        fetch("/api/schema"),
        fetch("/api/examples"),
        fetch("/api/databases"),
      ]);
      if (!hRes.ok) throw new Error("Health check failed");
      const [health, schemaData, examplesData, dbData] = await Promise.all([
        hRes.json(), sRes.json(), eRes.json(), dRes.json(),
      ]);
      setStatus(health);
      setSchema(schemaData.schema || {});
      setExamples(examplesData.examples || []);
      const names = dbData.databases || [];
      setDatabases(names);
      setSelectedDb(
        names.includes(health.database_name)
          ? health.database_name
          : names[0] || ""
      );
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load app data");
    }
  }, []);

  useEffect(() => { fetchInitialData(); }, [fetchInitialData]);

  /* ── keyboard shortcut ───────────────────────────────────────────────── */
  useEffect(() => {
    function onKey(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && canRun) {
        e.preventDefault();
        runQuery(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  /* ── query execution ─────────────────────────────────────────────────── */
  async function runQuery(forceConfirm = false) {
    if (!request.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request: request.trim(),
          generate_api: generateApi,
          dry_run: dryRun,
          confirm_high_risk: forceConfirm || confirmHighRisk,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "Query request failed");
      }
      const data = await res.json();
      setResult(data);
      setPlanOpen(false);
      setHistory((prev) =>
        [{ request: request.trim(), success: data.success, sql: data.sql, at: new Date().toLocaleTimeString() }, ...prev].slice(0, 8)
      );
      setWorkbench((prev) => [
        {
          id: Date.now(),
          request: request.trim(),
          sql: data.sql || "",
          success: data.success,
          risk_level: data.risk_level || "low",
          operation_type: data.operation_type || "",
          rows_count: Array.isArray(data.rows) ? data.rows.length : 0,
          affected_rows: data.affected_rows || 0,
          at: new Date().toLocaleTimeString(),
        },
        ...prev,
      ]);
      if (data.api_route) {
        setGeneratedApis((prev) => [
          { id: Date.now(), title: request.trim(), code: data.api_route, at: new Date().toLocaleTimeString() },
          ...prev,
        ]);
        setActiveTab("apis");
      }
    } catch (err) {
      setError(err.message || "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  /* ── database switch ─────────────────────────────────────────────────── */
  async function switchDatabase() {
    if (!selectedDb || switchingDb) return;
    setSwitchingDb(true);
    setError("");
    try {
      const res = await fetch("/api/database/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ database_name: selectedDb }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "Switch failed");
      }
      setResult(null);
      await fetchInitialData();
    } catch (err) {
      setError(err.message || "Unexpected error");
    } finally {
      setSwitchingDb(false);
    }
  }

  /* ── render ──────────────────────────────────────────────────────────── */
  return (
    <div className="page-shell">
      <div className="aurora" />

      <header className="hero">
        <div className="hero-text">
          <h1>SQL <span>Agent</span></h1>
          <p>Natural language → validated SQL · self-correction · FastAPI generation</p>
        </div>
        <div className="hero-status">
          {dot(status.database)} <span>Database</span>
          {dot(status.llm)} <span>LLM</span>
          <span className="provider-chip">{status.provider || "—"}</span>
        </div>
      </header>

      <main className="grid-layout">
        {/* ── sidebar ── */}
        <aside className="panel sidebar">
          <section className="sidebar-section">
            <span className="section-label">Active Database</span>
            <div className="db-switch-box">
              <select
                className="db-select"
                value={selectedDb}
                onChange={(e) => setSelectedDb(e.target.value)}
                disabled={databases.length === 0 || switchingDb}
              >
                {databases.length === 0 && <option value="">No databases</option>}
                {databases.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              <button
                type="button"
                className="btn ghost sm"
                onClick={switchDatabase}
                disabled={switchingDb || !selectedDb || selectedDb === status.database_name}
              >
                {switchingDb ? "Switching…" : "Switch"}
              </button>
            </div>
          </section>

          <section className="sidebar-section">
            <span className="section-label">Schema Explorer</span>
            <div className="schema-box">
              {Object.keys(schema).length === 0
                ? <p className="muted">No schema loaded.</p>
                : Object.entries(schema).map(([table, info]) => (
                    <details key={table} className="schema-table">
                      <summary>
                        <span className="table-icon">▸</span> {table}
                        <span className="col-count">{(info.columns || []).length} cols</span>
                      </summary>
                      <ul className="col-list">
                        {(info.columns || []).map((col) => (
                          <li key={col.name} className="col-row">
                            <span className="col-name">{col.name}</span>
                            <span className="col-type">{col.type}</span>
                            {col.key === "PRI" && <Badge label="PK" kind="pk" />}
                            {!col.nullable && col.key !== "PRI" && <Badge label="NN" kind="nn" />}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ))
              }
            </div>
          </section>

          <section className="sidebar-section">
            <span className="section-label">History</span>
            <div className="history-box">
              {history.length === 0
                ? <p className="muted">No queries yet.</p>
                : history.map((item, idx) => (
                    <button
                      key={`${item.at}-${idx}`}
                      type="button"
                      className="history-item"
                      onClick={() => setRequest(item.request)}
                      title={item.request}
                    >
                      {dot(item.success)}
                      <span className="history-text">{item.request}</span>
                      <time className="history-time">{item.at}</time>
                    </button>
                  ))
              }
            </div>
          </section>
        </aside>

        {/* ── workspace ── */}
        <section className="panel workspace">
          {/* tab bar */}
          <div className="tab-bar">
            <button
              className={`tab-btn ${activeTab === "query" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("query")}
            >
              Ask the Database
            </button>
            <button
              className={`tab-btn ${activeTab === "workbench" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("workbench")}
            >
              Workbench
              {workbench.length > 0 && <span className="tab-badge">{workbench.length}</span>}
            </button>
            <button
              className={`tab-btn ${activeTab === "apis" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("apis")}
            >
              Generated APIs
              {generatedApis.length > 0 && <span className="tab-badge">{generatedApis.length}</span>}
            </button>
          </div>

          {activeTab === "query" && (<>
          <div className="query-head">
            <h2>Ask the Database</h2>
            <div className="toggles-wrap">
              <Toggle checked={dryRun}          onChange={(e) => setDryRun(e.target.checked)}          label="Dry Run" />
              <Toggle checked={generateApi}      onChange={(e) => { setGenerateApi(e.target.checked); if (e.target.checked) setDryRun(false); }}      label="Generate API" />
              <Toggle checked={confirmHighRisk}  onChange={(e) => setConfirmHighRisk(e.target.checked)}  label="Confirm High-Risk" />
            </div>
          </div>

          <div className="input-wrap">
            <textarea
              ref={textareaRef}
              className="query-input"
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="e.g.  Show top 5 customers by total order value"
              rows={4}
            />
            <span className="char-hint">Ctrl + Enter to run</span>
          </div>

          <div className="actions-row">
            <button
              type="button"
              className="btn run"
              disabled={!canRun}
              onClick={() => runQuery(false)}
            >
              {loading ? "Running…" : "Run Query"}
            </button>
            <button type="button" className="btn ghost" onClick={fetchInitialData}>
              Refresh
            </button>
            <span className="db-chip">
              {status.database_name || "—"}
            </span>
          </div>

          {examples.length > 0 && (
            <div className="examples">
              {examples.map((ex) => (
                <button key={ex} type="button" className="example-pill" onClick={() => setRequest(ex)}>
                  {ex}
                </button>
              ))}
            </div>
          )}

          {error && <div className="notice error"><span className="notice-icon">✕</span>{error}</div>}

          {loading && <Spinner />}

          {result && !loading && (
            <div className="result-wrap">

              {/* metrics bar */}
              <div className="metrics-bar">
                <div className={`metric-chip ${result.success ? "chip-ok" : "chip-err"}`}>
                  {result.success ? "✓ Success" : "✕ Failed"}
                </div>
                <div className="metric-chip">
                  {Math.round(result.duration_ms || 0)} ms
                </div>
                <div className="metric-chip">
                  {rowCount || result.affected_rows || 0} rows
                </div>
                {result.correction_attempts > 0 && (
                  <div className="metric-chip chip-warn">
                    {result.correction_attempts} correction{result.correction_attempts !== 1 ? "s" : ""}
                  </div>
                )}
                <div className="metric-chip">
                  <RiskBadge level={result.risk_level} />
                </div>
                <div className="metric-chip">
                  {result.dry_run ? "Preview" : "Executed"}
                </div>
                {result.operation_type && (
                  <div className="metric-chip">{result.operation_type}</div>
                )}
              </div>

              {/* plan section */}
              {result.plan && result.plan.sub_tasks && result.plan.sub_tasks.length > 0 && (
                <div className="card plan-card">
                  <button
                    type="button"
                    className="card-toggle"
                    onClick={() => setPlanOpen((o) => !o)}
                  >
                    <span>Query Plan</span>
                    <span className="plan-meta">
                      <Badge label={result.plan.intent || "?"} kind="neutral" />
                      <RiskBadge level={result.plan.risk_assessment} />
                    </span>
                    <span className="chevron">{planOpen ? "▴" : "▾"}</span>
                  </button>
                  {planOpen && (
                    <div className="plan-body">
                      {result.plan.target_entities && result.plan.target_entities.length > 0 && (
                        <p className="plan-row">
                          <strong>Tables:</strong>{" "}
                          {result.plan.target_entities.map((t) => (
                            <Badge key={t} label={t} kind="table" />
                          ))}
                        </p>
                      )}
                      {result.plan.joins_needed && (
                        <p className="plan-row"><strong>Joins required:</strong> Yes</p>
                      )}
                      <ol className="sub-tasks">
                        {result.plan.sub_tasks.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ol>
                      {result.plan.notes && (
                        <p className="plan-note">{result.plan.notes}</p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* validation warnings */}
              {Array.isArray(result.validation_warnings) && result.validation_warnings.length > 0 && (
                <div className="notice warn">
                  <span className="notice-icon">⚠</span>
                  {result.validation_warnings.join(" · ")}
                </div>
              )}

              {/* execution plan / backup */}
              {result.execution_plan && result.execution_plan.summary && (
                <div className="notice info">
                  <strong>Plan:</strong> {result.execution_plan.summary}
                  {result.execution_plan.targets && result.execution_plan.targets.length > 0 &&
                    <span> · Targets: {result.execution_plan.targets.join(", ")}</span>}
                  {result.backup_path &&
                    <span> · Backup: <code>{result.backup_path}</code></span>}
                </div>
              )}

              {/* generated SQL */}
              {result.sql && (
                <div className="card code-card">
                  <div className="card-header">
                    <h3>Generated SQL</h3>
                    <CopyButton text={result.sql} />
                  </div>
                  <pre className="code-block">{result.sql}</pre>
                </div>
              )}

              {/* error */}
              {!result.success && (
                <div className="notice error">
                  <span className="notice-icon">✕</span>
                  {result.error || "Query failed"}
                </div>
              )}

              {/* confirm high-risk */}
              {!result.success && result.requires_confirmation && !dryRun && (
                <button type="button" className="btn run" onClick={() => runQuery(true)} disabled={loading}>
                  Confirm and Execute
                </button>
              )}

              {/* explanation */}
              {result.success && result.explanation && (
                <div className="notice info explanation">
                  <span className="notice-icon">💡</span>
                  {result.explanation}
                </div>
              )}

              {/* result table */}
              {result.success && Array.isArray(result.rows) && result.rows.length > 0 && (
                <div className="card table-card">
                  <div className="card-header">
                    <h3>Results <span className="row-badge">{result.rows.length} rows</span></h3>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          {Object.keys(result.rows[0]).map((col) => <th key={col}>{col}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {result.rows.map((row, ri) => (
                          <tr key={ri}>
                            {Object.entries(row).map(([k, v]) => (
                              <td key={`${ri}-${k}`}>{v === null ? <span className="null-val">NULL</span> : String(v)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* write op success */}
              {result.success && (!result.rows || result.rows.length === 0) && (
                <div className="notice info">
                  <span className="notice-icon">✓</span>
                  {result.affected_rows > 0
                    ? `${result.affected_rows} row(s) affected.`
                    : "Query executed successfully."}
                </div>
              )}

              {/* generated API — shown in Generated APIs tab */}
              {result.api_route && (
                <div className="notice info">
                  <span className="notice-icon">✓</span>
                  API route generated — view it in the <strong>Generated APIs</strong> tab.
                </div>
              )}
            </div>
          )}
          </>)}

          {activeTab === "workbench" && (
            <div className="wb-body">
              <div className="wb-header">
                <span className="wb-count">{workbench.length} {workbench.length === 1 ? "query" : "queries"}</span>
                {workbench.length > 0 && (
                  <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
                    <CopyButton text={workbench.map(i => i.sql || i.request).join("\n\n")} />
                    <button className="btn ghost sm" onClick={() => setWorkbench([])}>Clear all</button>
                  </div>
                )}
              </div>
              {workbench.length === 0 ? (
                <p className="muted wb-empty">Run a query — it will appear here.</p>
              ) : (
                <textarea
                  className="wb-editor"
                  value={workbench.map(i => i.sql || i.request).join("\n\n")}
                  onChange={(e) => {
                    const blocks = e.target.value.split(/\n\n+/);
                    setWorkbench((prev) =>
                      blocks.map((sql, idx) => ({
                        ...(prev[idx] || { id: Date.now() + idx, success: true }),
                        sql: sql,
                      }))
                    );
                  }}
                  spellCheck={false}
                />
              )}
            </div>
          )}

          {activeTab === "apis" && (
            <div className="apis-body">
              <div className="wb-header">
                <span className="wb-count">{generatedApis.length} {generatedApis.length === 1 ? "route" : "routes"}</span>
                {generatedApis.length > 0 && (
                  <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
                    <CopyButton text={generatedApis.map(a => `# ${a.title}\n${a.code}`).join("\n\n")} />
                    <button className="btn ghost sm" onClick={() => setGeneratedApis([])}>Clear all</button>
                  </div>
                )}
              </div>
              {generatedApis.length === 0 ? (
                <p className="muted wb-empty">Enable "Generate API" toggle and run a query — routes will appear here.</p>
              ) : (
                <div className="apis-list">
                  {generatedApis.map((api) => (
                    <div key={api.id} className="api-entry">
                      <div className="api-entry-header">
                        <span className="api-entry-title">{api.title}</span>
                        <time className="wb-time">{api.at}</time>
                        <CopyButton text={api.code} />
                        <button
                          className="btn ghost sm"
                          onClick={() => setGeneratedApis((prev) => prev.filter(a => a.id !== api.id))}
                        >✕</button>
                      </div>
                      <pre className="api-code">{api.code}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
