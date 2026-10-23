# MessWise — Autonomous Context-Aware Food Waste Optimization

A clean-room implementation for forecasting meal demand and producing practical kitchen preparation plans. This repository is independent; it does not reuse code or assets from earlier projects.

## Architecture

- **Frontend:** React + TypeScript + Vite
- **API:** FastAPI + Pydantic
- **Database:** PostgreSQL via SQLAlchemy 2 and Alembic (SQLite is the no-Docker local default)
- **Data pipeline:** accepts the August 2026 menu CSV directly; preserves prepared/consumed/leftover quantities, context fields, and item-specific unit hints
- **Analytics:** daily average waste-rate trends, item-level waste rates, meal comparisons, and CSV export; never sums mixed physical units into a misleading total
- **Forecasting:** attendance-scaled historical baseline blended with up to eight context-similar earlier records when liking, exam, temperature, rainfall, or demand-rate context is provided; MAE/RMSE/WAPE and chronological backtesting
- **Optimization:** deterministic batch sizing with explicit safety-buffer assumptions
- **Decision engine:** context notes, explanations, audit trail, and required human review
- **CI:** GitHub Actions runs backend tests and a frontend production build on pushes and PRs
- **Deployment:** Docker Compose for database, API, and dashboard

## Supplied dataset: August 2026

The supplied messwise_full_august_2026_menu_dataset.csv contains **973 item-level records** from **1–31 August 2026**, covering **145 distinct food items** across Breakfast (262 records), Lunch (292), Snacks (132), and Dinner (287). It includes source fields for liking score, exam intensity, temperature, rainfall, hostel attendance, historical demand rate, expected consumers, recommended preparation, actual prepared, consumed, leftover, waste-rate percentage, and a quantity-unit hint.

The adapter maps the original source fields as follows without discarding the source features:

- food_item → dish; recommended_preparation_portions → planned_portions
- consumed_portions → served_portions; leftover_portions → waste_portions
- hostel_attendance_estimate → attendance; the original attendance is also preserved separately
- prepared_portions, expected_consumers, waste_rate_pct, quantity_unit_hint, and contextual features remain available in history/export.

**Important unit rule:** the dataset mixes litres/kg, pieces, servings, and combined hints. MessWise therefore displays average row-level waste rates and groups dish metrics by unit hint; it does not present the sum of all leftovers as one physically meaningful total. The arithmetic mean of the supplied row-level waste_rate_pct values is approximately **6.07%**; this is an unweighted average across records, not a measured campus-wide mass balance. The source includes a field explicitly named synthetic_liking_score; treat the dataset as decision-support/demo input until its provenance and measurements are validated.

## Import the supplied CSV

1. Start the backend and frontend using the instructions below.
2. Open the dashboard and find **Import August 2026 menu CSV**.
3. Select the provided messwise_full_august_2026_menu_dataset.csv file.
4. If the database contains demo rows or another dataset, tick **Replace existing history**. This clears existing meal-history rows only after the uploaded CSV passes validation. Leave it unticked to append only new date/meal/item keys.
5. Click **Validate & import CSV**. Expect 973 rows to be imported into an empty history table. Then confirm the 145 item count, 31 service days, waste trends, and food-item options in meal planning.

A clean install no longer auto-seeds synthetic rows by default. To intentionally seed the small development fixture, set MESSWISE_SEED_DEMO_DATA=true before starting the API.

## Implementation phases

1. Requirements and modular-monolith architecture
2. CSV contract, synthetic sample, validation and import pipeline
3. Database models, schema migration and persistence layer
4. Data profiling and waste analytics foundation
5. Forecasting baseline and metric helpers
6. Portion and full-batch optimization
7. Explainable decisions and human approval
8. FastAPI endpoints and audit trail
9. Responsive React operator dashboard
10. Integration tests, CI, Docker configuration and documentation
11. **Data management:** validated CSV upload, duplicate-safe import and full-history CSV export
12. **Waste analytics:** daily waste trends, dish-level waste rates and summary insights
13. **Forecast evaluation:** chronological backtest with MAE, RMSE and WAPE when sufficient history exists
14. **Reliability:** API input bounds, upload size/type checks, review-state protection, health endpoint and Codespaces proxy
15. **Final integration:** automated API tests, frontend production build, run instructions and deployment path

## Run in GitHub Codespaces

Open the repository root at `/workspaces/finalfood`. Use two terminals.

**Terminal 1 — API:**

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Forward port **8000** in the Codespaces Ports tab. Test `/health` and open `/docs` from the forwarded port.

**Terminal 2 — dashboard:**

```bash
cd /workspaces/finalfood/frontend
npm install
npm run dev -- --host 0.0.0.0
```

Forward port **5173** and open it in the browser. Vite proxies `/api` requests to the backend on port 8000, so the browser does not need to access a local-machine `localhost:8000`. Keep both terminals running.

## Run locally (Mac/Linux)

Requirements: Python 3.11+, Node.js 20+, npm. Docker Desktop is optional.

**Terminal 1 — API** (run from repository root):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

**Terminal 2 — dashboard** (from repository root):

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173. API docs: http://localhost:8000/docs. Health: http://localhost:8000/health.

## CSV workflow

Use the dashboard's **Validate & import CSV** form, or run these commands from the repository root after activating the virtual environment:

```bash
python -m backend.app.data.cli validate data/raw/meal_history.csv
python -m backend.app.data.cli profile data/raw/meal_history.csv
python -m backend.app.data.cli import data/raw/meal_history.csv
```

CSV upload accepts files up to 5 MB. It supports both the generic contract and the original August menu dataset columns. Existing (date, meal, dish) keys are skipped unless the operator explicitly chooses replace-history. The dashboard can export all stored history and context fields as CSV.

## API endpoints

- `GET /health` — liveness check
- `GET /api/v1/summary` — record count, unique items, service days, average row-level waste rate, unit-grouped waste insights
- `GET /api/v1/history?limit=100` — recent history
- `GET /api/v1/analytics/trends` — daily served/waste totals and waste rate
- `GET /api/v1/analytics/dishes` — per-dish waste rate grouped by unit hint
- `GET /api/v1/analytics/meals` — average item-level waste rate by meal service
- `GET /api/v1/evaluation` — chronological backtest and MAE/RMSE/WAPE
- `POST /api/v1/data/upload` — multipart CSV upload and validation
- `GET /api/v1/data/export` — download stored history as CSV
- `POST /api/v1/forecast` — baseline forecast
- `POST /api/v1/plans` — create an auditable, review-required kitchen plan
- `GET /api/v1/plans` — recent plans
- `POST /api/v1/plans/{id}/feedback` — approve or reject a pending plan once

Interactive API docs: `/docs`.

## Checks

Run from the repository root:

```bash
pytest
cd frontend
npm install
npm run build
```

## Optional Docker Compose

```bash
docker compose up --build
```

Dashboard: http://localhost:8080; API docs: http://localhost:8000/docs; PostgreSQL is exposed on localhost port 5433. The sample password is only for local development.

## Dataset contract

One row per date, meal, and dish:
- `date`: YYYY-MM-DD
- `meal`: breakfast, lunch, snacks, or dinner
- `dish`: non-empty dish name
- `planned_portions`, `served_portions`, `waste_portions`, `attendance`: non-negative integers
- `waste_portions` must not exceed `served_portions`
- `is_weekend`: optional boolean
- `event_factor`: optional positive number, defaults to 1
- `weather`: optional text

## Model limitations and responsible use

Forecasting uses a recent median scaled by attendance, with an explicit 75%-of-attendance fallback if no suitable earlier history exists. When context values are supplied, the baseline is blended with earlier records whose liking score, exam intensity, temperature, rainfall, and historical demand rate are most similar. This is a transparent heuristic, not a trained causal model; its context similarity weights and 70/30 blend require validation on real data. The evaluation endpoint performs a chronological historical backtest; it does not prove future performance. Confidence labels are heuristic, and the baseline may underperform on holidays, special events, menu changes, or sudden attendance shifts.

The optimizer rounds forecasts to complete batches after a configurable buffer. This can create a surplus for large batch sizes, so use realistic vessel sizes and review every proposal. Context notes are shown to operators but do not silently change the numeric forecast.

The included CSV is synthetic sample data, not real campus-mess data. Do not report it as evidence of real waste reduction. MessWise is decision support, not automatic cooking control; staff must approve every production recommendation. Before real deployment, configure production secrets, managed database backups, HTTPS, access control/authentication, monitoring and privacy policies.
