import { FormEvent, useCallback, useEffect, useState } from "react";

const API = import.meta.env.VITE_API_BASE ?? "/api/v1";
const API_ROOT = API.endsWith("/api/v1") ? API.slice(0, -7) : "";

type Summary = {
  records: number; served_portions: number; waste_portions: number; waste_rate: number;
  top_waste_dishes: { dish: string; waste_portions: number }[];
};
type Plan = {
  id: number; date: string; meal: string; dish: string; forecast_portions: number;
  recommended_portions: number; batches: number; batch_size: number;
  expected_buffer_portions: number; status: string; explanation: string[];
};
type HistoryRow = {
  date: string; meal: string; dish: string; served_portions: number; waste_portions: number;
};
type Trend = { date: string; served_portions: number; waste_portions: number; waste_rate: number };
type Evaluation = {
  observations: number;
  metrics: { mae: number; rmse: number; wape: number } | null;
  note: string;
  methods?: Record<string, number>;
};

function todayLocal() {
  const d = new Date();
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, {
    ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || "Request failed");
  }
  return response.json() as Promise<T>;
}

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [targetDate, setTargetDate] = useState(todayLocal());
  const [meal, setMeal] = useState("lunch");
  const [dish, setDish] = useState("dal tadka");
  const [attendance, setAttendance] = useState("170");
  const [batchSize, setBatchSize] = useState("25");
  const [context, setContext] = useState("");
  const [trends, setTrends] = useState<Trend[]>([]);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [s, h, p, t, e] = await Promise.all([
        request<Summary>("/summary"), request<HistoryRow[]>("/history?limit=12"),
        request<Plan[]>("/plans?limit=8"), request<Trend[]>("/analytics/trends"),
        request<Evaluation>("/evaluation"),
      ]);
      setSummary(s); setHistory(h); setPlans(p); setTrends(t); setEvaluation(e); setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to connect to the API");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function submitPlan(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage(""); setError("");
    try {
      const result = await request<Plan>("/plans", {
        method: "POST",
        body: JSON.stringify({
          date: targetDate, meal, dish, attendance: Number(attendance),
          batch_size: Number(batchSize), minimum_buffer_pct: 0.05,
          extra_context: context.split("\n").map((v) => v.trim()).filter(Boolean),
        }),
      });
      setMessage("Plan created. Review the recommendation before cooking.");
      setPlans((current) => [result, ...current.filter((p) => p.id !== result.id)].slice(0, 8));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create plan");
    } finally { setBusy(false); }
  }


  async function uploadCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("historyCsv") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setUploading(true); setMessage(""); setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(API_ROOT + "/api/v1/data/upload", {
        method: "POST", body: form,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "CSV import failed");
      setMessage(`Imported ${body.inserted} new rows; skipped ${body.skipped_duplicates} duplicates.`);
      input.value = "";
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "CSV import failed");
    } finally { setUploading(false); }
  }

  function exportCsv() {
    window.open(API_ROOT + "/api/v1/data/export", "_blank", "noopener,noreferrer");
  }

  async function review(plan: Plan, approved: boolean) {
    try {
      await request("/plans/" + plan.id + "/feedback", {
        method: "POST",
        body: JSON.stringify({ approved, reviewer: "kitchen_operator", note: "Reviewed in dashboard" }),
      });
      setMessage(approved ? "Plan approved and audit updated." : "Plan rejected and audit updated.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record review");
    }
  }

  const wastePct = summary ? (summary.waste_rate * 100).toFixed(1) : "—";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">M</span><span>messwise<small>KITCHEN INTELLIGENCE</small></span></div>
        <div className="side-label">WORKSPACE</div>
        <a className="nav-item active" href="#overview"><span>⌂</span> Overview</a>
        <a className="nav-item" href="#plan"><span>◷</span> Meal planning</a>
        <a className="nav-item" href="#history"><span>▤</span> Meal history</a>
        <a className="nav-item" href="#reviews"><span>✓</span> Plan reviews</a>
        <div className="sidebar-bottom"><span className="status-dot" /> Demo data connected <small>Synthetic sample · not live mess data</small></div>
      </aside>

      <main className="main-content">
        <header className="topbar"><div><span className="eyebrow">MESS OPERATIONS / TODAY</span><h1>Good planning starts here.</h1><p>Turn yesterday’s plates into a more practical plan for tomorrow.</p></div><div className="today-chip">◷ <span>{new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</span></div></header>

        {error && <div className="alert error"><strong>Connection or request error</strong><span>{error}</span><button onClick={() => void refresh()}>Retry</button></div>}
        {message && <div className="alert success"><span>{message}</span><button onClick={() => setMessage("")}>Dismiss</button></div>}

        <section id="overview" className="metrics-grid">
          <article className="metric-card"><div className="metric-top"><span>Meals recorded</span><span className="metric-icon violet">▤</span></div><strong>{summary?.records ?? "—"}</strong><small>rows in sample history</small></article>
          <article className="metric-card"><div className="metric-top"><span>Portions served</span><span className="metric-icon green">◉</span></div><strong>{summary ? summary.served_portions.toLocaleString("en-IN") : "—"}</strong><small>across recorded meals</small></article>
          <article className="metric-card"><div className="metric-top"><span>Waste portions</span><span className="metric-icon orange">↘</span></div><strong>{summary ? summary.waste_portions.toLocaleString("en-IN") : "—"}</strong><small>reported leftover portions</small></article>
          <article className="metric-card"><div className="metric-top"><span>Waste rate</span><span className="metric-icon blue">%</span></div><strong>{wastePct}{summary ? "%" : ""}</strong><small>leftover / served</small></article>
        </section>


        <section className="content-grid phase-tools">
          <article className="panel">
            <div className="panel-heading"><div><span className="eyebrow">PHASE 11 · DATA MANAGEMENT</span><h2>Import real meal history</h2><p>Upload a CSV using the documented dataset columns. Existing records are never silently overwritten.</p></div></div>
            <form className="upload-form" onSubmit={(event) => void uploadCsv(event)}>
              <label>Meal history CSV<input name="historyCsv" type="file" accept=".csv,text/csv" required /></label>
              <div className="tool-actions"><button className="primary-button" type="submit" disabled={uploading}>{uploading ? "Validating and importing…" : "Validate & import CSV"}</button><button className="secondary-button" type="button" onClick={exportCsv}>Export all history ↓</button></div>
              <p className="helper">Maximum 5 MB. Required columns: date, meal, dish, planned_portions, served_portions, waste_portions, attendance. Invalid rows are rejected with an explanation.</p>
            </form>
          </article>
          <article className="panel">
            <div className="panel-heading"><div><span className="eyebrow">PHASE 13 · MODEL CHECK</span><h2>Forecast evaluation</h2><p>Chronological backtest on stored history.</p></div></div>
            {evaluation?.metrics ? <div className="evaluation-grid">
              <div><small>MAE</small><strong>{evaluation.metrics.mae}</strong><span>portions</span></div>
              <div><small>RMSE</small><strong>{evaluation.metrics.rmse}</strong><span>portions</span></div>
              <div><small>WAPE</small><strong>{(evaluation.metrics.wape * 100).toFixed(1)}%</strong><span>weighted error</span></div>
            </div> : <p className="empty-state">{evaluation?.note ?? "Loading evaluation…"}</p>}
            <p className="helper">{evaluation?.observations ?? 0} evaluable observations. Metrics describe historical baseline performance, not a guarantee of future accuracy.</p>
          </article>
        </section>

        <section className="panel table-panel">
          <div className="panel-heading table-heading"><div><span className="eyebrow">PHASE 12 · WASTE ANALYTICS</span><h2>Daily waste trend</h2><p>Daily served portions and reported leftovers.</p></div><span className="quiet-tag">{trends.length} days</span></div>
          {trends.length ? <div className="trend-list">{trends.slice(-14).map((trend) => {
            const maxWaste = Math.max(...trends.slice(-14).map((item) => item.waste_portions), 1);
            return <div className="trend-row" key={trend.date}><span>{trend.date}</span><div className="trend-bar"><div style={{ width: (trend.waste_portions / maxWaste * 100) + "%" }} /></div><strong>{trend.waste_portions}</strong><small>{(trend.waste_rate * 100).toFixed(1)}%</small></div>;
          })}</div> : <p className="empty-state">No trend data is available yet.</p>}
        </section>

        <section className="content-grid">
          <article className="panel planner" id="plan">
            <div className="panel-heading"><div><span className="eyebrow">DECISION SUPPORT</span><h2>Build a meal plan</h2><p>Use attendance and kitchen batch size to create a reviewable proposal.</p></div><span className="step-tag">01 / PLAN</span></div>
            <form onSubmit={submitPlan}>
              <div className="form-row">
                <label>Service date<input type="date" required value={targetDate} onChange={(e) => setTargetDate(e.target.value)} /></label>
                <label>Meal service<select value={meal} onChange={(e) => setMeal(e.target.value)}><option value="breakfast">Breakfast</option><option value="lunch">Lunch</option><option value="snacks">Snacks</option><option value="dinner">Dinner</option></select></label>
              </div>
              <label>Dish name<input required value={dish} onChange={(e) => setDish(e.target.value)} placeholder="e.g. dal tadka" /></label>
              <div className="form-row">
                <label>Expected attendance<input type="number" min="0" required value={attendance} onChange={(e) => setAttendance(e.target.value)} /></label>
                <label>Portions per batch<input type="number" min="1" required value={batchSize} onChange={(e) => setBatchSize(e.target.value)} /></label>
              </div>
              <label>Context notes <span className="optional">(optional)</span><textarea rows={2} value={context} onChange={(e) => setContext(e.target.value)} placeholder={"Rain expected\nSports event on campus"} /></label>
              <p className="helper">Notes are recorded for the operator. They do not automatically change the numeric forecast.</p>
              <button className="primary-button" type="submit" disabled={busy}>{busy ? "Building plan…" : "Generate kitchen plan"} <span>↗</span></button>
            </form>
          </article>

          <article className="panel waste-panel">
            <div className="panel-heading"><div><span className="eyebrow">WHERE TO LOOK</span><h2>Top waste dishes</h2><p>Start improvement with the largest recorded leftovers.</p></div></div>
            {summary?.top_waste_dishes.length ? <div className="waste-list">{summary.top_waste_dishes.map((item, i) => {
              const max = Math.max(...summary.top_waste_dishes.map((x) => x.waste_portions), 1);
              return <div className="waste-item" key={item.dish}><div className="waste-row"><span><b className="rank">{String(i + 1).padStart(2, "0")}</b>{item.dish}</span><strong>{item.waste_portions} <small>portions</small></strong></div><div className="bar-track"><div className="bar-fill" style={{ width: (item.waste_portions / max * 100) + "%" }} /></div></div>;
            })}</div> : <div className="empty-state">Loading waste insights…</div>}
            <div className="panel-note"><span>✳</span><p>Sample observations are synthetic. Replace them with approved mess records before making operational decisions.</p></div>
          </article>
        </section>

        <section className="panel table-panel" id="history">
          <div className="panel-heading table-heading"><div><span className="eyebrow">RECENT OBSERVATIONS</span><h2>Meal history</h2></div><span className="quiet-tag">Last {history.length} rows</span></div>
          <div className="table-wrap"><table><thead><tr><th>Service date</th><th>Meal</th><th>Dish</th><th>Served</th><th>Waste</th><th>Waste rate</th></tr></thead><tbody>
            {history.map((row, i) => <tr key={row.date + row.meal + row.dish + i}><td>{row.date}</td><td><span className="meal-pill">{row.meal}</span></td><td className="dish-cell">{row.dish}</td><td>{row.served_portions}</td><td>{row.waste_portions}</td><td>{row.served_portions ? (row.waste_portions / row.served_portions * 100).toFixed(1) : "0.0"}%</td></tr>)}
          </tbody></table></div>
        </section>

        <section className="panel reviews-panel" id="reviews">
          <div className="panel-heading table-heading"><div><span className="eyebrow">HUMAN-IN-THE-LOOP</span><h2>Plans awaiting review</h2><p>MessWise suggests. Kitchen staff decides.</p></div><span className="review-count">{plans.filter((p) => p.status === "pending_review").length} pending</span></div>
          {plans.length ? <div className="review-list">{plans.map((plan) => <div className="review-card" key={plan.id}><div className="review-main"><div><span className="meal-pill">{plan.meal}</span><h3>{plan.dish}</h3><small>{plan.date} · Plan #{plan.id}</small></div><span className={"status-pill " + plan.status}>{plan.status.replace("_", " ")}</span></div><div className="plan-stats"><div><small>Forecast</small><strong>{plan.forecast_portions}</strong></div><div><small>Prepare</small><strong>{plan.recommended_portions}</strong></div><div><small>Full batches</small><strong>{plan.batches} × {plan.batch_size}</strong></div></div><details><summary>Why this plan?</summary><ul>{plan.explanation?.map((line, i) => <li key={i}>{line}</li>)}</ul></details>{plan.status === "pending_review" && <div className="review-actions"><button onClick={() => void review(plan, true)} className="approve-button">✓ Approve plan</button><button onClick={() => void review(plan, false)} className="reject-button">Reject</button></div>}</div>)}</div> : <div className="empty-state">No plans yet. Generate a plan above to start a review.</div>}
        </section>
        <footer><span>MESSWISE</span> Built for practical meal decisions · Forecasts are estimates, not instructions to cook automatically.</footer>
      </main>
    </div>
  );
}
