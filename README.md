# MessWise — Autonomous Context-Aware Food Waste Optimization

A clean-room implementation for forecasting meal demand and producing practical kitchen preparation plans. This repository is independent; it does not reuse code or assets from earlier projects.

## Architecture

- **Frontend:** React + TypeScript + Vite
- **API:** FastAPI + Pydantic
- **Database:** PostgreSQL via SQLAlchemy 2 and Alembic (SQLite is the no-Docker local default)
- **Data pipeline:** CSV validation, normalization, profiling, and idempotent database import
- **Forecasting:** transparent baseline estimates with MAE/RMSE/WAPE evaluation helpers
- **Optimization:** deterministic batch sizing with explicit safety-buffer assumptions
- **Decision engine:** context notes, explanations, and required human review
- **CI:** GitHub Actions runs backend tests and a frontend production build on pushes and PRs
- **Deployment:** Docker Compose for database, API, and dashboard

## Phases 1–10

1. Requirements and architecture foundation
2. CSV contract, synthetic sample, validation and import pipeline
3. Database models, schema migration and persistence layer
4. Data profiling and waste analytics
5. Forecasting baseline and metric helpers
6. Portion and full-batch optimization
7. Context-aware explainable decisions and staff approval
8. Versioned FastAPI endpoints
9. Responsive operator dashboard
10. Integration, CI, Docker path and tests

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

The API seeds the database on first start from the included sample CSV only when the meal-history table is empty. From then on, history, summary, forecasts, and plans use persisted database data.

**Terminal 2 — dashboard** (from repository root):

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173. API docs: http://localhost:8000/docs. Health: http://localhost:8000/health.

## CSV workflow

Activate the Python environment at the repository root first:

```bash
python -m backend.app.data.cli validate data/raw/meal_history.csv
python -m backend.app.data.cli profile data/raw/meal_history.csv
python -m backend.app.data.cli import data/raw/meal_history.csv
```

The import command inserts new (date, meal, dish) keys and skips existing keys. It intentionally does not overwrite history silently. The API reads the database after startup seeding; import additional approved CSV rows before using them in a forecast.

## Checks

```bash
pytest
cd frontend && npm run build
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

## Current model limits

Forecasting uses a recent median scaled by attendance where possible, with an explicit 75%-of-attendance fallback if no suitable earlier history exists. This is a transparent baseline, **not yet a trained high-accuracy model**. Confidence labels are heuristic. Proper chronological holdout testing and comparison against more advanced models should be done once enough approved operational history exists.

The optimizer rounds forecasts to complete batches after a configurable buffer. That can create a large surplus for big vessel sizes; set a batch size that matches the real kitchen workflow and review every proposal. Context notes are surfaced to the operator but do not silently change the numeric forecast.

## Data and safety note

The included CSV is synthetic sample data, not real campus-mess data. Do not report it as evidence of real waste reduction. MessWise is decision support, not automatic cooking control; staff must approve every production recommendation.
