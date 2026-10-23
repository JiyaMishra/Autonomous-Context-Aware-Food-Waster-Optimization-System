# MessWise — Autonomous Context-Aware Food Waste Optimization

A clean-room implementation for forecasting meal demand and producing practical kitchen preparation plans. This repository was built independently; no code or assets are copied from previous projects.

## Architecture

- **Frontend:** React + TypeScript + Vite
- **API:** FastAPI + Pydantic
- **Database:** PostgreSQL via SQLAlchemy 2 and Alembic migrations (SQLite is the local no-Docker default)
- **Data pipeline:** CSV validation, normalization, profiling, and idempotent database import
- **Forecasting:** transparent baseline forecasts and MAE/RMSE/WAPE metric helpers
- **Optimization:** deterministic, constrained batch sizing with explicit buffer assumptions
- **Decision engine:** context notes, explanations, and human review status
- **Testing:** pytest backend checks and TypeScript/Vite production build
- **Deployment:** Docker Compose for PostgreSQL, API, and web interface

## Phase map (1–10)

1. Requirements, architecture, repository foundation
2. CSV data contract, synthetic starter data, validation/import pipeline
3. Database models, Alembic migration, and session/repository foundations
4. Exploratory data profiling and waste summaries
5. Demand forecasting baseline and metric evaluation helpers
6. Portion and full-batch optimizer
7. Context-aware, explainable proposal with mandatory staff review
8. Versioned FastAPI endpoints
9. Operator-focused React dashboard
10. Integrated local/Docker run paths, API checks, and testing setup

## Local quick start (Mac/Linux)

Prerequisites: Python 3.11+, Node.js 20+, npm. Docker Desktop is optional for the local SQLite setup.

**1. Start the API (Terminal 1, from the repository root):**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

Open http://localhost:8000/docs to inspect the API. Health check: http://localhost:8000/health.

**2. Start the dashboard (Terminal 2, from the repository root):**

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173.

**3. Validate and profile the bundled CSV (from repository root with the venv active):**

```bash
python -m backend.app.data.cli validate data/raw/meal_history.csv
python -m backend.app.data.cli profile data/raw/meal_history.csv
python -m backend.app.data.cli import data/raw/meal_history.csv
```

The import command inserts new date/meal/dish keys and skips already imported keys. It does not overwrite existing rows.

**4. Run tests and build checks:**

```bash
pytest
cd frontend && npm run build
```

**5. Optional Docker setup:**

```bash
docker compose up --build
```

Dashboard: http://localhost:8080; API docs: http://localhost:8000/docs; PostgreSQL is published on localhost port 5433. The example database password is for local development only.

## CSV data contract

One row per date, meal, and dish:

| Column | Meaning |
|---|---|
| `date` | YYYY-MM-DD |
| `meal` | breakfast, lunch, snacks, or dinner |
| `dish` | non-empty dish name |
| `planned_portions` | non-negative integer |
| `served_portions` | non-negative integer |
| `waste_portions` | non-negative integer, no greater than served portions |
| `attendance` | non-negative integer |
| `is_weekend` | optional boolean |
| `event_factor` | optional positive multiplier, default 1.0 |
| `weather` | optional text |

## Forecasting and optimizer limits

The current forecast is a baseline (recent median, scaled by attendance where possible); it is **not** a trained high-accuracy model. When there is no matching earlier history, the documented fallback estimates 75% of attendance times the event factor. Confidence labels are heuristic. Evaluation metrics are provided, but a robust time-based model comparison and calibration still need to be run on real data.

Plans round up to complete batch sizes after an explicitly configured buffer. This can result in a large surplus when batch size is large, so use practical vessel/batch units for a real kitchen. Operator context is recorded in the explanation but intentionally does not silently alter forecast numbers.

## Data and safety notes

The bundled CSV is synthetic and exists only for development/testing. It is not actual college-mess data and must not be used to claim real waste reduction. MessWise is decision support, **not** unattended kitchen control: review every plan, verify food-safety and serving assumptions, and use approved operational data before acting on recommendations.

## Current project state

The repository now contains the initial end-to-end implementation scaffold for phases 1–10. Run the local commands above to install dependencies and verify the project in your environment; this ChatGPT session cannot run GitHub-hosted CI or your Mac's browser.
