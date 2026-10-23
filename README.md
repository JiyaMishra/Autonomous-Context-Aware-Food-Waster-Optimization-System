# MessWise — Autonomous Context-Aware Food Waste Optimization

A clean-room implementation for forecasting meal demand and producing practical kitchen preparation plans. This repository is independent and does not copy code or assets from any prior project.

## Architecture

- **Frontend:** React + TypeScript + Vite
- **API:** FastAPI + Pydantic
- **Database:** PostgreSQL via SQLAlchemy 2 and Alembic
- **Data pipeline:** CSV validation, normalization, profiling, and database import
- **Forecasting:** baseline models first, model evaluation with time-ordered validation
- **Optimization:** deterministic, constrained batch sizing with transparent assumptions
- **Decision engine:** context-aware proposal + explanation + human review status
- **Testing:** pytest for backend/data/model/decision logic; frontend build checks
- **Deployment:** Docker Compose for local development; production settings documented separately

## Phase plan (1–10)

1. Requirements, architecture, repository foundation
2. CSV data contract, synthetic starter data, validation/import pipeline
3. Database models, migrations, and repository layer
4. Exploratory data analysis and data-quality report
5. Demand forecasting baselines and evaluation
6. Kitchen quantity and batch optimization
7. Context-aware decision engine with explanations and approval flow
8. Versioned FastAPI endpoints
9. Operator-focused React dashboard
10. End-to-end integration, health checks, tests, and local run instructions

## Quick start

Prerequisites: Python 3.11+, Node.js 20+, npm. Docker Desktop is optional unless using PostgreSQL through Compose.

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
source .venv/bin/activate
pytest
```

### CSV pipeline

```bash
python -m backend.app.data.cli validate data/raw/meal_history.csv
python -m backend.app.data.cli profile data/raw/meal_history.csv
```

The bundled dataset is synthetic and intended for development/testing only. It is not real campus-mess data.

## Data contract

The CSV is one row per date, meal, and dish:
- `date` (YYYY-MM-DD)
- `meal` (breakfast, lunch, snacks, dinner)
- `dish` (non-empty name)
- `planned_portions` (non-negative integer)
- `served_portions` (non-negative integer)
- `waste_portions` (non-negative integer)
- `attendance` (non-negative integer)
- `is_weekend` (optional boolean)
- `event_factor` (optional positive number; default 1.0)
- `weather` (optional string)

Waste must not exceed served portions. For real data, confirm whether portions, weights, and preparation-vessel capacities match local kitchen practice before using recommendations.

## Safety / operating assumptions

MessWise produces **decision support**, not unattended kitchen commands. Every plan includes its inputs and assumptions. Staff must review plans before production. Do not use synthetic results as evidence of actual waste reduction.

## Project status

Phases 1–10 have code scaffolding and a runnable integration path in this initial build. Replace synthetic data with approved real operational data before drawing real-world conclusions.
