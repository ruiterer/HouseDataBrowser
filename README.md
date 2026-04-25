# HouseDataBrowser

A web app to explore the data in your home InfluxDB **using natural language** —
no InfluxQL typing required. Ask questions like "compare my electricity production
in summer 2024 vs summer 2023" and get back a chart, a table, a written summary, and
the generated query.

## Architecture (high-level)

- **Backend**: FastAPI (Python 3.12) — runs an LLM agent loop, owns the InfluxDB
  connection, enforces a read-only query gate, indexes the schema for RAG.
- **Frontend**: React + TypeScript (Vite) — chat UX, Plotly charts, schema browser,
  dashboard of pinned charts.
- **State**: SQLite (chat history, pinned charts, schema annotations).
- **LLM**: pluggable. Claude API by default; swap to Ollama (e.g. on a Raspberry
  Pi 5) by changing `LLM_PROVIDER` in `.env`.
- **Deployment**: Docker container on the same LAN as your existing InfluxDB.

The full plan and phase breakdown lives at
`/Users/erik/.claude/plans/i-have-stored-a-noble-anchor.md`.

## Status: Phase 1 — Skeleton & connectivity

What works today:
- Backend boots, connects to InfluxDB 1.x, exposes `/api/health`.
- Read-only InfluxQL safety filter with full test coverage.
- React skeleton with Chat / Dashboard / Schema routes and a live health badge.
- Multi-stage Docker build that bundles the React build into the FastAPI container.

Phases 2-5 (schema discovery, agent loop, pinned dashboard, Ollama provider) are
planned but not implemented yet.

## Getting started

### 1. Configure

```bash
cp .env.example .env
# Edit .env: point INFLUX_HOST/PORT/DATABASE at your existing InfluxDB,
# set ANTHROPIC_API_KEY, etc.
```

### 2. Local dev (two processes)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to the backend on port 8000.

### 3. Run tests

```bash
cd backend
pytest
```

### 4. Production (Docker)

```bash
docker compose up --build -d
```

Open http://localhost:8000. The image bundles the built React app served by FastAPI.

## Project layout

```
backend/
  app/
    config.py            # Pydantic settings, .env-driven
    influx/
      safety.py          # Read-only InfluxQL gate (the security boundary)
      client.py          # Async wrapper over influxdb-python (v1)
    api/health.py        # /api/health
    main.py              # FastAPI app + lifespan
  tests/test_safety.py   # Tests for the safety filter
frontend/
  src/
    pages/               # Chat, Dashboard, Schema
    components/          # HealthBadge, ...
.env.example
Dockerfile               # Multi-stage: node build -> python runtime
docker-compose.yml
```
