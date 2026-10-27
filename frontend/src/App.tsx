import { FormEvent, useCallback, useEffect, useState } from "react";

const API = import.meta.env.VITE_API_BASE ?? "/api/v1";
const API_ROOT = API.endsWith("/api/v1") ? API.slice(0, -7) : "";

type Summary = {
  records: number;
  unique_dishes: number;
  service_days: number;
  waste_rate: number;
  average_waste_rate_pct: number;
  top_waste_dishes: {
    dish: string;
    records: number;
    average_waste_rate_pct: number;
    total_waste_in_item_unit: number;
    quantity_unit_hint: string;
  }[];
  unit_breakdown: {
    unit: string;
    records: number;
    average_waste_rate_pct: number;
  }[];
};

type Plan = {
  id: number;
  date: string;
  meal: string;
  dish: string;
  forecast_portions: number;
  recommended_portions: number;
  batches: number;
  batch_size: number;
  expected_buffer_portions: number;
  status: string;
  explanation: string[];
  auto_predicted_attendance?: number | null;
  reviewer?: string | null;
  review_note?: string | null;
};

type HistoryRow = {
  date: string;
  meal: string;
  dish: string;
  served_portions: number;
  waste_portions: number;
  planned_portions?: number;
  prepared_portions?: number | null;
  waste_rate_pct?: number | null;
  quantity_unit_hint?: string | null;
  synthetic_liking_score?: number | null;
  exam_intensity?: number | null;
  expected_consumers?: number | null;
};

type Trend = {
  date: string;
  records: number;
  average_waste_rate_pct: number;
  waste_rate: number;
};

type MealMetric = {
  meal: string;
  records: number;
  average_waste_rate_pct: number;
  average_liking_score: number | null;
  average_exam_intensity: number | null;
};

type MenuItem = {
  dish: string;
  template_date: string;
  served_portions: number | null;
  prepared_portions: number | null;
  waste_portions: number | null;
  attendance: number | null;
  synthetic_liking_score: number | null;
  exam_intensity: number | null;
  temperature_c: number | null;
  rainfall_mm: number | null;
  historical_demand_rate: number | null;
  quantity_unit_hint: string | null;
  waste_rate_pct: number | null;
};

type Evaluation = {
  observations: number;
  metrics: { mae: number; rmse: number; wape: number } | null;
  note: string;
  methods?: Record<string, number>;
};

type AttendancePrediction = {
  predicted_attendance: number;
  predicted_absent: number;
  total_registered: number;
  turnout_pct: number;
  weather: { temperature_c: number; rainfall_mm: number; source: string };
  exam: {
    intensity: number;
    label: string | null;
    is_exam_period: boolean;
    is_ramp_up: boolean;
    days_until_exam?: number;
    effect: string;
  };
  campus_situation?: string | null;
  campus_factor?: number;
  confidence: string;
  method: string;
  training_samples: number;
  factors: {
    weather_effect: string;
    exam_effect: string;
    day_effect: string;
    campus_effect?: string;
  };
  factors_summary: string[];
};

function todayLocal() {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-");
}

function offsetDate(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || "Request failed");
  }
  return response.json() as Promise<T>;
}

export default function App() {
  // Navigation tab state
  const [activeTab, setActiveTab] = useState<"planner" | "reviews" | "analytics" | "data" | "history">("planner");

  // Core data states
  const [summary, setSummary] = useState<Summary | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [dishOptions, setDishOptions] = useState<string[]>([]);
  const [mealMetrics, setMealMetrics] = useState<MealMetric[]>([]);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);

  // Status & Feedback states
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [replaceExisting, setReplaceExisting] = useState(false);

  // Meal planning form states
  const [targetDate, setTargetDate] = useState(todayLocal());
  const [meal, setMeal] = useState("lunch");
  const [dish, setDish] = useState("Dal Tadka");
  const [batchSize, setBatchSize] = useState("25");
  const [context, setContext] = useState("");
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [menuLoading, setMenuLoading] = useState(false);
  const [menuError, setMenuError] = useState("");

  // Plan reviews filter state
  const [reviewFilter, setReviewFilter] = useState<"all" | "pending_review" | "approved" | "rejected">("all");

  // Analytics filter state
  const [unitFilter, setUnitFilter] = useState<string>("all");

  // AI Attendance Prediction states
  const [aiPrediction, setAiPrediction] = useState<AttendancePrediction | null>(null);
  const [aiPredictionLoading, setAiPredictionLoading] = useState(false);
  const [aiPredictionError, setAiPredictionError] = useState("");

  // Contextual parameter overrides
  const [examSetting, setExamSetting] = useState<"none" | "quiz" | "cat1" | "cat2" | "fat" | "auto">("none");
  const [weatherSetting, setWeatherSetting] = useState<"auto" | "clear" | "hot" | "light_rain" | "heavy_rain" | "custom">("auto");
  const [customTemp, setCustomTemp] = useState("28");
  const [customRain, setCustomRain] = useState("0");
  const [situationSetting, setSituationSetting] = useState<"normal" | "weekend_home" | "college_fest" | "holiday" | "custom">("normal");
  const [customFactorPct, setCustomFactorPct] = useState("100");
  const [paramsDrawerOpen, setParamsDrawerOpen] = useState(false);

  // Chatbot state
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpQuestion, setHelpQuestion] = useState("");
  const [submittedHelpQuestion, setSubmittedHelpQuestion] = useState("");

  // Refresh all dashboard data
  const refresh = useCallback(async () => {
    try {
      const [s, h, p, t, e, d, m] = await Promise.all([
        request<Summary>("/summary"),
        request<HistoryRow[]>("/history?limit=15"),
        request<Plan[]>("/plans?limit=15"),
        request<Trend[]>("/analytics/trends"),
        request<Evaluation>("/evaluation"),
        request<Array<{ dish: string }>>("/analytics/dishes"),
        request<MealMetric[]>("/analytics/meals"),
      ]);
      setSummary(s);
      setHistory(h);
      setPlans(p);
      setTrends(t);
      setEvaluation(e);
      setDishOptions(Array.from(new Set(d.map((item) => item.dish))).sort((x, y) => x.localeCompare(y)));
      setMealMetrics(m);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to connect to the MessWise API");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Construct parameter payload for AI Attendance model
  const getPredictionPayload = useCallback(() => {
    let exam_intensity: number | null = null;
    let exam_label: string | null = null;
    if (examSetting === "none") {
      exam_intensity = 0.0;
      exam_label = "No exams (regular schedule)";
    } else if (examSetting === "quiz") {
      exam_intensity = 0.25;
      exam_label = "Minor Quizzes / Quiz prep";
    } else if (examSetting === "cat1") {
      exam_intensity = 0.6;
      exam_label = "CAT-1 Exams";
    } else if (examSetting === "cat2") {
      exam_intensity = 0.75;
      exam_label = "CAT-2 Exams";
    } else if (examSetting === "fat") {
      exam_intensity = 0.95;
      exam_label = "FAT Final Exams";
    }

    let temperature_c: number | null = null;
    let rainfall_mm: number | null = null;
    if (weatherSetting === "clear") {
      temperature_c = 27.0;
      rainfall_mm = 0.0;
    } else if (weatherSetting === "hot") {
      temperature_c = 36.0;
      rainfall_mm = 0.0;
    } else if (weatherSetting === "light_rain") {
      temperature_c = 25.0;
      rainfall_mm = 5.0;
    } else if (weatherSetting === "heavy_rain") {
      temperature_c = 23.0;
      rainfall_mm = 25.0;
    } else if (weatherSetting === "custom") {
      temperature_c = Number(customTemp) || 28.0;
      rainfall_mm = Number(customRain) || 0.0;
    }

    let campus_situation: string | null = null;
    let campus_factor = 1.0;
    if (situationSetting === "weekend_home") {
      campus_situation = "Students went home (long weekend)";
      campus_factor = 0.7;
    } else if (situationSetting === "college_fest") {
      campus_situation = "College fest / Hackathon on campus";
      campus_factor = 1.1;
    } else if (situationSetting === "holiday") {
      campus_situation = "Special holiday / Campus closure";
      campus_factor = 0.6;
    } else if (situationSetting === "custom") {
      campus_situation = "Custom occupancy adjustment";
      campus_factor = Math.max(0.1, (Number(customFactorPct) || 100) / 100);
    }

    return {
      date: targetDate,
      meal,
      exam_intensity,
      exam_label,
      temperature_c,
      rainfall_mm,
      campus_situation,
      campus_factor,
    };
  }, [targetDate, meal, examSetting, weatherSetting, customTemp, customRain, situationSetting, customFactorPct]);

  // Fetch AI attendance prediction
  const fetchAiPrediction = useCallback(async () => {
    setAiPredictionLoading(true);
    setAiPredictionError("");
    try {
      const payload = getPredictionPayload();
      const result = await request<AttendancePrediction>("/predict-attendance", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setAiPrediction(result);
    } catch (e) {
      setAiPredictionError(e instanceof Error ? e.message : "Could not predict attendance.");
      setAiPrediction(null);
    } finally {
      setAiPredictionLoading(false);
    }
  }, [getPredictionPayload]);

  useEffect(() => {
    void fetchAiPrediction();
  }, [fetchAiPrediction]);

  // Load menu items for chosen date & meal
  const loadMenu = useCallback(async () => {
    setMenuLoading(true);
    setMenuError("");
    try {
      const result = await request<{
        date: string;
        meal: string;
        template_day: number;
        items: MenuItem[];
      }>("/menu?date=" + encodeURIComponent(targetDate) + "&meal=" + encodeURIComponent(meal));
      setMenuItems(result.items);
      if (result.items.length) {
        if (!result.items.some((item) => item.dish === dish)) {
          setDish(result.items[0].dish);
        }
      } else {
        setDish("");
        setMenuError("No menu found for this service.");
      }
    } catch (e) {
      setMenuItems([]);
      setMenuError(e instanceof Error ? e.message : "Could not load menu items.");
    } finally {
      setMenuLoading(false);
    }
  }, [targetDate, meal, dish]);

  useEffect(() => {
    void loadMenu();
  }, [loadMenu]);

  const selectedMenuItem = menuItems.find((item) => item.dish === dish);

  // Live estimated portions computation for preview
  const liveExpectedAttendance = aiPrediction?.predicted_attendance ?? 350;
  const liveDemandRate = selectedMenuItem?.historical_demand_rate ?? 0.65;
  const liveEstimatedPortions = Math.round(liveExpectedAttendance * liveDemandRate);
  const liveBufferPortions = Math.round(liveEstimatedPortions * 0.05);
  const liveBatchInt = Math.max(1, Number(batchSize) || 25);
  const liveBatches = Math.ceil((liveEstimatedPortions + liveBufferPortions) / liveBatchInt);
  const liveTotalRecommended = liveBatches * liveBatchInt;

  // Submit kitchen plan
  async function submitPlan(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const payload = getPredictionPayload();
      const result = await request<Plan>("/plans", {
        method: "POST",
        body: JSON.stringify({
          date: targetDate,
          meal,
          dish,
          attendance: null,
          batch_size: Number(batchSize),
          minimum_buffer_pct: 0.05,
          extra_context: context.split("\n").map((v) => v.trim()).filter(Boolean),
          synthetic_liking_score: null,
          exam_intensity: payload.exam_intensity,
          exam_label: payload.exam_label,
          temperature_c: payload.temperature_c,
          rainfall_mm: payload.rainfall_mm,
          campus_situation: payload.campus_situation,
          campus_factor: payload.campus_factor,
          historical_demand_rate: null,
        }),
      });
      setMessage(`Plan created for ${result.dish} with ${result.batches} batch(es) (${result.recommended_portions} portions). Review it below!`);
      setPlans((current) => [result, ...current.filter((p) => p.id !== result.id)]);
      setActiveTab("reviews");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create kitchen plan");
    } finally {
      setBusy(false);
    }
  }

  // Review a plan (Approve / Reject)
  async function review(plan: Plan, approved: boolean) {
    try {
      await request("/plans/" + plan.id + "/feedback", {
        method: "POST",
        body: JSON.stringify({
          approved,
          reviewer: "kitchen_operator",
          note: approved ? "Approved in dashboard" : "Rejected in dashboard",
        }),
      });
      setMessage(approved ? `Plan #${plan.id} for ${plan.dish} approved!` : `Plan #${plan.id} rejected.`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record review");
    }
  }

  // Clear all prepared plans
  async function clearAllPlans() {
    if (!window.confirm("Are you sure you want to clear all prepared meal plans?")) return;
    try {
      await request("/plans", { method: "DELETE" });
      setMessage("All prepared meal plans have been cleared.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not clear plans");
    }
  }

  // Upload and import CSV
  async function uploadCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("historyCsv") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage("");
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("replace_existing", String(replaceExisting));
      const response = await fetch(API_ROOT + "/api/v1/data/upload", {
        method: "POST",
        body: form,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "CSV import failed");
      setMessage(`${body.replaced_existing ? "Replaced previous history. " : ""}Imported ${body.inserted} rows; skipped ${body.skipped_duplicates} duplicates.`);
      input.value = "";
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "CSV import failed");
    } finally {
      setUploading(false);
    }
  }

  function exportCsv() {
    window.open(API_ROOT + "/api/v1/data/export", "_blank", "noopener,noreferrer");
  }

  // Chatbot response generator
  const helpAnswer = (question: string) => {
    const q = question.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
    const has = (...words: string[]) => words.some((word) => q.includes(word));
    const dateLabel = new Date(targetDate + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "long" });
    const currentAttendance = aiPrediction ? String(aiPrediction.predicted_attendance) : "AI predicting...";
    const contextStr = `Currently viewing: ${dateLabel}, ${meal}, ${dish}. Expected attendance: ${currentAttendance} students.`;

    if (has("hello", "hi", "hey")) return `Hello! I'm your MessWise kitchen assistant. You can ask me practical mess questions like 'What if 150 students arrive?', 'Why so much food?', or 'How does batch size work?' ${contextStr}`;
    if (has("only", "fewer", "less", "more", "attendance", "turnout", "came", "come")) return `MessWise predicts attendance using weather, exams, and campus schedules. If attendance drops unexpectedly (e.g. students went home for a festival or long weekend), click 'Tune prediction parameters' in the planner and select 'Students Went Home'. The AI will immediately rescale the portions! ${contextStr}`;
    if (has("too much", "too many", "waste", "why so much", "shortage", "leftover")) return `MessWise starts with past demand, scales by predicted attendance, adds a 5% safety buffer, and rounds up to whole kitchen batches (pots/cookers). You can adjust the batch size or tune real-world parameters to fine-tune the recommendation. ${contextStr}`;
    if (has("rain", "weather", "hot", "exam", "fat", "cat")) return `Weather and exams directly affect dining turnout. Heavy rain typically reduces mess turnout by ~8–12%, while during FAT exam weeks students eat at odd hours or skip snacks. Use the 'Tune prediction parameters' toggle to tell the AI if severe weather or exam cramming is occurring today!`;
    if (has("batch", "size", "degchi", "pot", "vessel", "cooker")) return `A batch is your kitchen's standard preparation unit (e.g., 1 large degchi of rice = 25 servings). When you set Batch Size to 25, MessWise rounds food preparation up to the nearest multiple of 25 so kitchen staff can prepare whole pots instead of fractional amounts.`;
    if (has("approve", "reject", "review")) return `MessWise suggests, but kitchen operators decide. In the 'Plans awaiting review' tab, you can inspect the suggested batches and buffer, then click '✓ Approve' to confirm or 'Reject' if kitchen conditions require a different decision.`;
    return `You can ask me anything about kitchen batch sizes, weather adjustments, or how to generate and approve plans. Try asking: 'Why did it suggest this amount?' or 'What if it rains today?' ${contextStr}`;
  };

  const pendingPlansCount = plans.filter((p) => p.status === "pending_review").length;
  const filteredPlans = plans.filter((p) => {
    if (reviewFilter === "all") return true;
    return p.status === reviewFilter;
  });

  const filteredDishes = summary?.top_waste_dishes.filter((item) => {
    if (unitFilter === "all") return true;
    return (item.quantity_unit_hint || "").toLowerCase().includes(unitFilter.toLowerCase());
  }) ?? [];

  return (
    <div className="app-shell">
      {/* Sleek Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">M</span>
          <div className="brand-text">
            <span className="brand-title">MessWise</span>
            <span className="brand-subtitle">Culinary AI</span>
          </div>
        </div>

        <div className="side-label">WORKSPACE</div>
        <nav className="sidebar-nav">
          <button
            type="button"
            className={`nav-item ${activeTab === "planner" ? "active" : ""}`}
            onClick={() => setActiveTab("planner")}
          >
            <span className="nav-item-icon">🍱</span>
            <span>Meal Planning</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "reviews" ? "active" : ""}`}
            onClick={() => setActiveTab("reviews")}
          >
            <span className="nav-item-icon">📋</span>
            <span>Plans & Approvals</span>
            {pendingPlansCount > 0 && <span className="nav-item-badge">{pendingPlansCount}</span>}
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "analytics" ? "active" : ""}`}
            onClick={() => setActiveTab("analytics")}
          >
            <span className="nav-item-icon">📊</span>
            <span>Waste Analytics</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "data" ? "active" : ""}`}
            onClick={() => setActiveTab("data")}
          >
            <span className="nav-item-icon">📁</span>
            <span>Data & Model Hub</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "history" ? "active" : ""}`}
            onClick={() => setActiveTab("history")}
          >
            <span className="nav-item-icon">▤</span>
            <span>Meal History</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-status-indicator">
            <span className="status-dot-pulse" />
            <span>AI Decision Engine Active</span>
          </div>
          <p>Autonomous weather, calendar & batch optimization active.</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {/* Topbar with Live Campus Status */}
        <header className="topbar">
          <div className="topbar-left">
            <span className="eyebrow">CAMPUS MESS OPERATIONS</span>
            <h1>Autonomous Meal Demand & Waste Optimization</h1>
            <p>Practical kitchen prep forecasting powered by weather, exams, and attendance context.</p>
          </div>

          <div className="topbar-right">
            <div className="campus-pill weather">
              <span>🌤️</span>
              <span>{aiPrediction ? `${aiPrediction.weather.temperature_c}°C · Clear` : "Weather Active"}</span>
            </div>

            <div className="campus-pill exam">
              <span>📚</span>
              <span>{aiPrediction?.exam.is_exam_period ? aiPrediction.exam.label : "Regular Classes (No Exams)"}</span>
            </div>

            <div className="topbar-date-card">
              <span>📅</span>
              <span>{new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</span>
            </div>
          </div>
        </header>

        {/* Global Alerts */}
        {error && (
          <div className="app-alert error">
            <span>⚠ {error}</span>
            <button type="button" onClick={() => void refresh()}>Retry Connection</button>
          </div>
        )}
        {message && (
          <div className="app-alert success">
            <span>✓ {message}</span>
            <button type="button" onClick={() => setMessage("")}>Dismiss</button>
          </div>
        )}

        {/* Workspace Quick Tabs */}
        <nav className="workspace-tabs" aria-label="Workspace Sections">
          <button
            type="button"
            className={`workspace-tab-btn ${activeTab === "planner" ? "active" : ""}`}
            onClick={() => setActiveTab("planner")}
          >
            <span>🍱 Meal Planner & AI Forecast</span>
          </button>

          <button
            type="button"
            className={`workspace-tab-btn ${activeTab === "reviews" ? "active" : ""}`}
            onClick={() => setActiveTab("reviews")}
          >
            <span>📋 Plans & Approvals</span>
            <span className="workspace-tab-badge">{plans.length}</span>
          </button>

          <button
            type="button"
            className={`workspace-tab-btn ${activeTab === "analytics" ? "active" : ""}`}
            onClick={() => setActiveTab("analytics")}
          >
            <span>📊 Waste Analytics & Trends</span>
          </button>

          <button
            type="button"
            className={`workspace-tab-btn ${activeTab === "data" ? "active" : ""}`}
            onClick={() => setActiveTab("data")}
          >
            <span>📁 Data & Model Hub</span>
          </button>

          <button
            type="button"
            className={`workspace-tab-btn ${activeTab === "history" ? "active" : ""}`}
            onClick={() => setActiveTab("history")}
          >
            <span>▤ Meal History ({history.length})</span>
          </button>
        </nav>

        {/* Overview Metric KPIs */}
        <section className="metrics-grid">
          <article className="metric-card">
            <div className="metric-top">
              <span className="metric-label">Dataset Records</span>
              <span className="metric-icon-wrap emerald">▤</span>
            </div>
            <strong>{summary?.records ?? "973"}</strong>
            <small>Item × service observations</small>
          </article>

          <article className="metric-card">
            <div className="metric-top">
              <span className="metric-label">Unique Dishes</span>
              <span className="metric-icon-wrap indigo">◉</span>
            </div>
            <strong>{summary?.unique_dishes ?? "145"}</strong>
            <small>Distinct campus food recipes</small>
          </article>

          <article className="metric-card">
            <div className="metric-top">
              <span className="metric-label">Service Days</span>
              <span className="metric-icon-wrap amber">▦</span>
            </div>
            <strong>{summary?.service_days ?? "31"}</strong>
            <small>Days tracked in August 2026</small>
          </article>

          <article className="metric-card">
            <div className="metric-top">
              <span className="metric-label">Avg Waste Rate</span>
              <span className="metric-icon-wrap rose">%</span>
            </div>
            <strong>{summary ? `${summary.average_waste_rate_pct.toFixed(1)}%` : "6.1%"}</strong>
            <small>Unweighted mean plate waste</small>
          </article>
        </section>

        {/* TAB 1: MEAL PLANNER & AI FORECAST */}
        {activeTab === "planner" && (
          <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">STEP 1 · SELECT SERVICE & ITEM</span>
                  <h2>Build Kitchen Preparation Plan</h2>
                  <p>Pick a date, meal, and specific dish. The AI predicts student attendance and optimizes batch sizes.</p>
                </div>
              </div>

              <form onSubmit={submitPlan} className="planner-form">
                {/* Visual Meal Selector Pills */}
                <div className="form-group">
                  <label>
                    <span>Meal Service</span>
                    <span className="hint">Select which meal to prepare</span>
                  </label>
                  <div className="meal-selector-grid">
                    {[
                      { id: "breakfast", label: "Breakfast", emoji: "🥞" },
                      { id: "lunch", label: "Lunch", emoji: "🍛" },
                      { id: "snacks", label: "Snacks", emoji: "☕" },
                      { id: "dinner", label: "Dinner", emoji: "🍲" },
                    ].map((m) => (
                      <button
                        type="button"
                        key={m.id}
                        className={`meal-option-card ${meal === m.id ? "selected" : ""}`}
                        onClick={() => setMeal(m.id)}
                      >
                        <span className="meal-emoji">{m.emoji}</span>
                        <span>{m.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Date Selection */}
                <div className="form-row">
                  <div className="form-group">
                    <label>
                      <span>Service Date</span>
                      <span className="hint">Day number maps to August menu</span>
                    </label>
                    <input
                      type="date"
                      className="form-input"
                      required
                      value={targetDate}
                      onChange={(e) => setTargetDate(e.target.value)}
                    />
                    <div className="quick-date-chips">
                      <button
                        type="button"
                        className={`chip-btn ${targetDate === todayLocal() ? "active" : ""}`}
                        onClick={() => setTargetDate(todayLocal())}
                      >
                        Today
                      </button>
                      <button
                        type="button"
                        className={`chip-btn ${targetDate === offsetDate(1) ? "active" : ""}`}
                        onClick={() => setTargetDate(offsetDate(1))}
                      >
                        Tomorrow
                      </button>
                    </div>
                  </div>

                  {/* Batch Size Selection */}
                  <div className="form-group">
                    <label>
                      <span>Kitchen Batch Size</span>
                      <span className="hint">Portions per pot / cooker</span>
                    </label>
                    <input
                      type="number"
                      min="1"
                      className="form-input"
                      required
                      value={batchSize}
                      onChange={(e) => setBatchSize(e.target.value)}
                      placeholder="e.g. 25"
                    />
                  </div>
                </div>

                {/* Dish Selector */}
                <div className="form-group">
                  <label>
                    <span>Food Item / Dish</span>
                    <span className="hint">{menuItems.length} dishes available on this service</span>
                  </label>
                  <select
                    className="form-select"
                    required
                    value={dish}
                    onChange={(e) => setDish(e.target.value)}
                    disabled={menuLoading || menuItems.length === 0}
                  >
                    <option value="">{menuLoading ? "Loading menu items…" : "Choose a food item"}</option>
                    {menuItems.map((item) => (
                      <option key={item.dish} value={item.dish}>
                        {item.dish} ({item.quantity_unit_hint ?? "servings"})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Historical Dish Reference */}
                {selectedMenuItem && (
                  <div className="dish-history-banner">
                    <div>
                      <strong>Historical Performance:</strong> {selectedMenuItem.dish}
                    </div>
                    <div className="dish-history-stats">
                      <span>Prepared: <strong>{selectedMenuItem.prepared_portions ?? "—"}</strong></span>
                      <span>Eaten: <strong>{selectedMenuItem.served_portions ?? "—"}</strong></span>
                      <span>Leftover: <strong>{selectedMenuItem.waste_portions ?? "—"}</strong></span>
                      <span>Unit: <strong>{selectedMenuItem.quantity_unit_hint ?? "servings"}</strong></span>
                    </div>
                  </div>
                )}

                {/* AI Attendance Prediction Card 2.0 */}
                <div className="ai-prediction-card">
                  <div className="ai-prediction-header">
                    <div className="ai-robot-badge">🤖</div>
                    <div>
                      <h4>AI Attendance Prediction</h4>
                      <p>Gradient Boosted Trees trained on campus attendance patterns</p>
                    </div>
                    <button
                      type="button"
                      className="ai-refresh-icon-btn"
                      onClick={() => void fetchAiPrediction()}
                      disabled={aiPredictionLoading}
                      title="Recalculate prediction"
                    >
                      {aiPredictionLoading ? "⟳" : "↻"}
                    </button>
                  </div>

                  {aiPrediction && !aiPredictionLoading && (
                    <>
                      <div className="ai-kpi-grid">
                        <div className="ai-kpi-box primary">
                          <small>Expected Students</small>
                          <strong>{aiPrediction.predicted_attendance}</strong>
                          <span>diners</span>
                        </div>
                        <div className="ai-kpi-box">
                          <small>Expected Absent</small>
                          <strong>{aiPrediction.predicted_absent}</strong>
                          <span>students</span>
                        </div>
                        <div className="ai-kpi-box">
                          <small>Turnout Rate</small>
                          <strong>{aiPrediction.turnout_pct}%</strong>
                          <span>of {aiPrediction.total_registered}</span>
                        </div>
                      </div>

                      <div className="turnout-bar-wrap">
                        <div className="turnout-bar-header">
                          <span>Mess Hall Capacity Utilization</span>
                          <strong>{aiPrediction.turnout_pct}%</strong>
                        </div>
                        <div className="turnout-track">
                          <div
                            className="turnout-fill"
                            style={{ width: `${Math.min(100, aiPrediction.turnout_pct)}%` }}
                          />
                        </div>
                      </div>

                      <div className="ai-factors-chips">
                        <div className="context-tag">
                          <span>🌤️</span>
                          <span>{aiPrediction.weather.temperature_c}°C, {aiPrediction.weather.rainfall_mm}mm rain</span>
                        </div>

                        <div className="context-tag">
                          <span>📚</span>
                          <span>{aiPrediction.exam.intensity > 0 ? (aiPrediction.exam.label ?? "Exams active") : "No active exams"}</span>
                        </div>

                        {aiPrediction.campus_situation && (
                          <div className="context-tag">
                            <span>🏛️</span>
                            <span>{aiPrediction.campus_situation}</span>
                          </div>
                        )}

                        <div className="context-tag">
                          <span>📅</span>
                          <span>{aiPrediction.factors.day_effect}</span>
                        </div>
                      </div>
                    </>
                  )}

                  {/* Real-World Context Adjuster */}
                  <div className="ai-params-section">
                    <button
                      type="button"
                      className="params-toggle-bar"
                      onClick={() => setParamsDrawerOpen(!paramsDrawerOpen)}
                    >
                      <span>⚙️ Tune Real-World Parameters (tell the AI what's happening today)</span>
                      <span>{paramsDrawerOpen ? "▲ Close" : "▼ Tune"}</span>
                    </button>

                    {paramsDrawerOpen && (
                      <div className="params-card-expanded">
                        <p style={{ fontSize: "11.5px", color: "var(--slate-600)" }}>
                          If there are unusual conditions today (e.g. students went home for a festival or severe rainfall), adjust parameters below. The AI model recalculates attendance in real-time.
                        </p>

                        <div className="form-row">
                          <div className="form-group">
                            <label>Exam Schedule</label>
                            <select
                              className="form-select"
                              value={examSetting}
                              onChange={(e) => setExamSetting(e.target.value as any)}
                            >
                              <option value="none">No Exams (Regular Schedule)</option>
                              <option value="quiz">Minor Quizzes (25% intensity)</option>
                              <option value="cat1">CAT-1 Exams (60% intensity)</option>
                              <option value="cat2">CAT-2 Exams (75% intensity)</option>
                              <option value="fat">FAT Final Exams (95% intensity)</option>
                            </select>
                          </div>

                          <div className="form-group">
                            <label>Weather Context</label>
                            <select
                              className="form-select"
                              value={weatherSetting}
                              onChange={(e) => setWeatherSetting(e.target.value as any)}
                            >
                              <option value="auto">Live Weather API (Automatic)</option>
                              <option value="clear">Clear & Pleasant (27°C, 0mm)</option>
                              <option value="hot">Intense Heatwave (36°C, 0mm)</option>
                              <option value="light_rain">Light Rain / Drizzle (25°C, 5mm)</option>
                              <option value="heavy_rain">Heavy Downpour (23°C, 25mm)</option>
                            </select>
                          </div>
                        </div>

                        <div className="form-group">
                          <label>Campus Situation</label>
                          <select
                            className="form-select"
                            value={situationSetting}
                            onChange={(e) => setSituationSetting(e.target.value as any)}
                          >
                            <option value="normal">Normal Campus Schedule (100% presence)</option>
                            <option value="weekend_home">Students Went Home / Long Weekend (~30% drop)</option>
                            <option value="college_fest">College Fest / Hackathon (+10% turnout)</option>
                            <option value="holiday">Special Holiday (~40% drop)</option>
                          </select>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Live Planning Preview */}
                <div className="plan-live-preview">
                  <div className="plan-live-preview-title">
                    <span>⚡ Live Planning Preview</span>
                  </div>
                  <div className="preview-numbers-grid">
                    <div className="preview-number-box">
                      <small>Expected Eaten</small>
                      <strong>{liveEstimatedPortions}</strong>
                      <div style={{ fontSize: "10px", color: "var(--slate-400)" }}>portions</div>
                    </div>
                    <div className="preview-number-box">
                      <small>+5% Safety Buffer</small>
                      <strong>+{liveBufferPortions}</strong>
                      <div style={{ fontSize: "10px", color: "var(--slate-400)" }}>reserve buffer</div>
                    </div>
                    <div className="preview-number-box">
                      <small>Suggested Cook</small>
                      <strong>{liveBatches} × {liveBatchInt}</strong>
                      <div style={{ fontSize: "10px", color: "var(--emerald-600)", fontWeight: 700 }}>
                        {liveTotalRecommended} portions
                      </div>
                    </div>
                  </div>
                </div>

                {/* Optional context notes */}
                <div className="form-group">
                  <label>
                    <span>Operator Context Notes</span>
                    <span className="hint">(Recorded for human review)</span>
                  </label>
                  <textarea
                    rows={2}
                    className="form-textarea"
                    value={context}
                    onChange={(e) => setContext(e.target.value)}
                    placeholder="e.g. Hostels have a floor meeting tonight, kitchen gas line under maintenance..."
                  />
                </div>

                {/* Generate Button */}
                <button
                  type="submit"
                  className="btn-generate-plan"
                  disabled={busy || !dish}
                >
                  <span>{busy ? "Calculating Optimized Plan…" : "Generate Kitchen Plan"}</span>
                  <span>↗</span>
                </button>
              </form>
          </section>
        )}

        {/* TAB 2: PLANS & APPROVALS (HUMAN-IN-THE-LOOP) */}
        {activeTab === "reviews" && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">HUMAN-IN-THE-LOOP OVERSIGHT</span>
                <h2>Kitchen Plans & Approvals</h2>
                <p>MessWise suggests. Kitchen staff decides and reviews before cooking begins.</p>
              </div>

              <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                {/* Status Filters */}
                <div style={{ display: "flex", gap: "6px" }}>
                  {(["all", "pending_review", "approved", "rejected"] as const).map((filter) => (
                    <button
                      key={filter}
                      type="button"
                      className={`chip-btn ${reviewFilter === filter ? "active" : ""}`}
                      onClick={() => setReviewFilter(filter)}
                    >
                      {filter === "all" ? "All Plans" : filter.replace("_", " ")}
                    </button>
                  ))}
                </div>

                {plans.length > 0 && (
                  <button
                    type="button"
                    onClick={clearAllPlans}
                    className="chip-btn"
                    style={{ borderColor: "var(--rose-200)", color: "var(--rose-600)" }}
                    title="Clear all generated plans"
                  >
                    Clear All Plans
                  </button>
                )}
              </div>
            </div>

            {filteredPlans.length ? (
              <div className="reviews-grid">
                {filteredPlans.map((plan) => (
                  <div key={plan.id} className="review-card">
                    <div className="review-card-header">
                      <div className="review-card-title">
                        <span className={`meal-badge ${plan.meal}`}>{plan.meal}</span>
                        <h3>{plan.dish}</h3>
                        <small>{plan.date} · Plan #{plan.id}</small>
                      </div>

                      <span className={`status-badge ${plan.status}`}>
                        {plan.status.replace("_", " ")}
                      </span>
                    </div>

                    <div className="review-stats-bar">
                      <div>
                        <small>Expected Eaten</small>
                        <strong>{plan.forecast_portions}</strong>
                      </div>
                      <div>
                        <small>Prepare</small>
                        <strong>{plan.recommended_portions}</strong>
                      </div>
                      <div>
                        <small>Batches</small>
                        <strong>{plan.batches} × {plan.batch_size}</strong>
                      </div>
                    </div>

                    <div className="review-explanation">
                      <p>
                        <strong>Suggested to cook:</strong> {plan.recommended_portions} portions in {plan.batches} batch(es) of {plan.batch_size}.
                      </p>
                      <p style={{ marginTop: "4px", fontSize: "11.5px", color: "var(--slate-500)" }}>
                        Includes +{plan.expected_buffer_portions} portions extra buffer to avoid shortages.
                      </p>
                    </div>

                    {plan.status === "pending_review" ? (
                      <div className="review-actions-row">
                        <button
                          type="button"
                          className="btn-approve"
                          onClick={() => void review(plan, true)}
                        >
                          ✓ Approve Plan
                        </button>
                        <button
                          type="button"
                          className="btn-reject"
                          onClick={() => void review(plan, false)}
                        >
                          ✕ Reject
                        </button>
                      </div>
                    ) : (
                      <div style={{ fontSize: "11px", color: "var(--slate-400)", textAlign: "center" }}>
                        Reviewed by {plan.reviewer ?? "kitchen staff"}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--slate-500)" }}>
                <p style={{ fontSize: "16px", fontWeight: 700, color: "var(--slate-700)" }}>No plans awaiting review</p>
                <p style={{ fontSize: "13px", marginTop: "6px" }}>
                  Select a specific food item in the Meal Planner tab above and click &ldquo;Generate Kitchen Plan&rdquo;.
                </p>
                <button
                  type="button"
                  onClick={() => setActiveTab("planner")}
                  className="btn-approve"
                  style={{ maxWidth: "200px", margin: "16px auto 0" }}
                >
                  Go to Meal Planner ↗
                </button>
              </div>
            )}
          </section>
        )}

        {/* TAB 3: WASTE ANALYTICS & TRENDS */}
        {activeTab === "analytics" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "22px" }}>
            {/* Top Waste Dishes with Unit Filter */}
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">MENU ITEM EFFICIENCY</span>
                  <h2>Food Items by Waste Rate</h2>
                  <p>Filter by physical unit to compare like-for-like leftovers without mixing physical quantities.</p>
                </div>

                <div style={{ display: "flex", gap: "6px" }}>
                  {["all", "servings", "litres_or_kg", "pieces_or_servings"].map((u) => (
                    <button
                      key={u}
                      type="button"
                      className={`chip-btn ${unitFilter === u ? "active" : ""}`}
                      onClick={() => setUnitFilter(u)}
                    >
                      {u === "all" ? "All Units" : u.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "12px" }}>
                {filteredDishes.map((item, index) => {
                  const pct = item.average_waste_rate_pct;
                  const severity = pct > 10 ? "high" : pct > 6 ? "medium" : "low";
                  return (
                    <div key={item.dish} className="waste-dish-row">
                      <div className="waste-dish-info">
                        <span>
                          <span className="waste-dish-rank">#{index + 1}</span>
                          {item.dish}
                        </span>
                        <strong style={{ color: severity === "high" ? "var(--rose-600)" : "inherit" }}>
                          {pct.toFixed(1)}%
                        </strong>
                      </div>
                      <div className="waste-bar-track">
                        <div
                          className={`waste-bar-fill ${severity}`}
                          style={{ width: `${Math.min(100, pct * 8)}%` }}
                        />
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10.5px", color: "var(--slate-400)" }}>
                        <span>Unit: {item.quantity_unit_hint}</span>
                        <span>{item.records} servings recorded</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Daily Waste Trends */}
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">CHRONOLOGICAL PERFORMANCE</span>
                  <h2>Daily Waste Rate Trends</h2>
                  <p>Daily unweighted row-average waste percentage across all served items.</p>
                </div>
                <span className="chip-btn active">{trends.length} service days</span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {trends.slice(-14).map((trend) => {
                  const maxRate = Math.max(...trends.slice(-14).map((t) => t.average_waste_rate_pct), 1);
                  return (
                    <div
                      key={trend.date}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "100px 1fr 60px 80px",
                        alignItems: "center",
                        gap: "14px",
                        fontSize: "12px",
                      }}
                    >
                      <span style={{ fontWeight: 600, color: "var(--slate-700)" }}>{trend.date}</span>
                      <div className="waste-bar-track" style={{ height: "8px" }}>
                        <div
                          className="waste-bar-fill medium"
                          style={{ width: `${(trend.average_waste_rate_pct / maxRate) * 100}%` }}
                        />
                      </div>
                      <strong style={{ textAlign: "right" }}>{trend.average_waste_rate_pct.toFixed(1)}%</strong>
                      <span style={{ textAlign: "right", color: "var(--slate-400)" }}>{trend.records} items</span>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Meal Service Comparison */}
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">SERVICE COMPARISON</span>
                  <h2>Waste by Meal Service</h2>
                  <p>Compare breakfast, lunch, snacks, and dinner performance.</p>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px" }}>
                {mealMetrics.map((m) => (
                  <div
                    key={m.meal}
                    style={{
                      padding: "18px",
                      background: "var(--slate-50)",
                      border: "1px solid var(--slate-200)",
                      borderRadius: "var(--radius-lg)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                    }}
                  >
                    <span className={`meal-badge ${m.meal}`} style={{ alignSelf: "flex-start" }}>{m.meal}</span>
                    <strong style={{ fontSize: "24px", fontFamily: "var(--font-display)", color: "var(--slate-900)", marginTop: "6px" }}>
                      {m.average_waste_rate_pct.toFixed(1)}%
                    </strong>
                    <span style={{ fontSize: "11.5px", color: "var(--slate-500)" }}>{m.records} total meal rows</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {/* TAB 4: DATA & MODEL HUB */}
        {activeTab === "data" && (
          <section className="content-grid">
            {/* CSV Management */}
            <article className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">DATASET INGESTION</span>
                  <h2>Import & Export Meal Data</h2>
                  <p>Import CSV menu data with item-specific units and environmental context preserved.</p>
                </div>
              </div>

              <form onSubmit={uploadCsv} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div className="form-group">
                  <label>Select CSV File</label>
                  <input
                    name="historyCsv"
                    type="file"
                    accept=".csv,text/csv"
                    required
                    style={{ padding: "10px", border: "1.5px dashed var(--slate-300)", borderRadius: "var(--radius-md)" }}
                  />
                </div>

                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--slate-700)" }}>
                  <input
                    type="checkbox"
                    checked={replaceExisting}
                    onChange={(e) => setReplaceExisting(e.target.checked)}
                  />
                  <span>Replace existing dataset (clears current meal history before importing)</span>
                </label>

                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <button type="submit" className="btn-approve" disabled={uploading}>
                    {uploading ? "Validating & Importing…" : "Validate & Import CSV"}
                  </button>
                  <button type="button" onClick={exportCsv} className="chip-btn" style={{ padding: "10px 16px" }}>
                    Export All History ↓
                  </button>
                </div>
              </form>
            </article>

            {/* Model Evaluation Metrics */}
            <article className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">CHRONOLOGICAL BACKTESTING</span>
                  <h2>Forecast Model Evaluation</h2>
                  <p>Historical backtest error metrics on stored campus meal data.</p>
                </div>
              </div>

              {evaluation?.metrics ? (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px", textAlign: "center" }}>
                  <div style={{ padding: "16px", background: "var(--slate-50)", borderRadius: "var(--radius-md)" }}>
                    <small style={{ fontSize: "10px", fontWeight: 700, color: "var(--slate-400)" }}>MAE</small>
                    <strong style={{ display: "block", fontSize: "22px", fontFamily: "var(--font-display)", color: "var(--slate-900)" }}>
                      {evaluation.metrics.mae}
                    </strong>
                    <span style={{ fontSize: "10.5px", color: "var(--slate-500)" }}>portions</span>
                  </div>

                  <div style={{ padding: "16px", background: "var(--slate-50)", borderRadius: "var(--radius-md)" }}>
                    <small style={{ fontSize: "10px", fontWeight: 700, color: "var(--slate-400)" }}>RMSE</small>
                    <strong style={{ display: "block", fontSize: "22px", fontFamily: "var(--font-display)", color: "var(--slate-900)" }}>
                      {evaluation.metrics.rmse}
                    </strong>
                    <span style={{ fontSize: "10.5px", color: "var(--slate-500)" }}>portions</span>
                  </div>

                  <div style={{ padding: "16px", background: "var(--slate-50)", borderRadius: "var(--radius-md)" }}>
                    <small style={{ fontSize: "10px", fontWeight: 700, color: "var(--slate-400)" }}>WAPE</small>
                    <strong style={{ display: "block", fontSize: "22px", fontFamily: "var(--font-display)", color: "var(--slate-900)" }}>
                      {(evaluation.metrics.wape * 100).toFixed(1)}%
                    </strong>
                    <span style={{ fontSize: "10.5px", color: "var(--slate-500)" }}>weighted error</span>
                  </div>
                </div>
              ) : (
                <p style={{ color: "var(--slate-500)", fontSize: "12px" }}>{evaluation?.note ?? "Evaluating model…"}</p>
              )}

              <p style={{ fontSize: "11.5px", color: "var(--slate-400)", marginTop: "16px" }}>
                Evaluated across {evaluation?.observations ?? 0} historical observations.
              </p>
            </article>
          </section>
        )}

        {/* TAB 5: MEAL HISTORY TABLE */}
        {activeTab === "history" && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">RAW RECORD LOG</span>
                <h2>Historical Observations</h2>
                <p>Quantities are preserved in each recipe’s specific physical measurement unit.</p>
              </div>
              <span className="chip-btn active">Showing {history.length} records</span>
            </div>

            <div className="data-table-container">
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Meal</th>
                    <th>Dish</th>
                    <th>Prepared</th>
                    <th>Served</th>
                    <th>Leftover</th>
                    <th>Waste Rate</th>
                    <th>Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((row, i) => (
                    <tr key={`${row.date}-${row.meal}-${row.dish}-${i}`}>
                      <td>{row.date}</td>
                      <td>
                        <span className={`meal-badge ${row.meal}`}>{row.meal}</span>
                      </td>
                      <td style={{ fontWeight: 600, color: "var(--slate-900)" }}>{row.dish}</td>
                      <td>{row.prepared_portions ?? row.planned_portions ?? "—"}</td>
                      <td>{row.served_portions}</td>
                      <td>{row.waste_portions}</td>
                      <td style={{ fontWeight: 600 }}>
                        {typeof row.waste_rate_pct === "number"
                          ? `${row.waste_rate_pct.toFixed(1)}%`
                          : "0.0%"}
                      </td>
                      <td>{row.quantity_unit_hint ?? "servings"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Footer */}
        <footer style={{ marginTop: "24px", textAlign: "center", fontSize: "12px", color: "var(--slate-400)" }}>
          <strong>MESSWISE CULINARY INTELLIGENCE</strong> · Autonomous Food Waste Optimization · Designed for Campus Kitchen Staff
        </footer>
      </main>

      {/* Modern AI Kitchen Chatbot ("Ask MessWise") */}
      <div className="help-widget">
        {helpOpen && (
          <div className="help-modal-panel">
            <div className="help-modal-header">
              <div>
                <h4>Ask MessWise Assistant</h4>
                <small style={{ fontSize: "11px", color: "var(--slate-500)" }}>Kitchen advisor & workflow guidance</small>
              </div>
              <button
                type="button"
                onClick={() => setHelpOpen(false)}
                style={{ fontSize: "18px", color: "var(--slate-500)" }}
              >
                ✕
              </button>
            </div>

            <div className="help-modal-body">
              <p style={{ fontSize: "12px", color: "var(--slate-600)" }}>
                Ask like you would ask a kitchen colleague about batch sizes, low turnout, or weather effects:
              </p>

              <div className="help-prompt-chips">
                {[
                  "Only 200 students came today—what should I change?",
                  "Why is it suggesting so much food?",
                  "What if it rains today?",
                  "What does batch size mean?",
                  "What should I check before approving?",
                ].map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="help-chip"
                    onClick={() => {
                      setHelpQuestion(q);
                      setSubmittedHelpQuestion(q);
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>

              {submittedHelpQuestion && (
                <div className="help-answer-bubble">
                  <strong style={{ display: "block", marginBottom: "4px", color: "var(--slate-900)" }}>
                    Q: {submittedHelpQuestion}
                  </strong>
                  <p>{helpAnswer(submittedHelpQuestion)}</p>
                </div>
              )}
            </div>

            <form
              className="help-modal-footer"
              onSubmit={(e) => {
                e.preventDefault();
                const q = helpQuestion.trim();
                if (q) {
                  setSubmittedHelpQuestion(q);
                  setHelpQuestion("");
                }
              }}
            >
              <input
                className="help-input"
                value={helpQuestion}
                onChange={(e) => setHelpQuestion(e.target.value)}
                placeholder="Ask about batch sizes, weather, or planning…"
              />
              <button type="submit" className="help-send-btn">
                Ask
              </button>
            </form>
          </div>
        )}

        <button
          type="button"
          className="help-launcher-btn"
          onClick={() => setHelpOpen(!helpOpen)}
        >
          <span>✦</span>
          <span>{helpOpen ? "Close Assistant" : "Ask MessWise"}</span>
        </button>
      </div>
    </div>
  );
}
