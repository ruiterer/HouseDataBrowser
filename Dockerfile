# --- Stage 1: build the React frontend -------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# --- Stage 2: backend image with the built static assets bundled in --------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/
RUN pip install --upgrade pip && \
    pip install -e /app/backend

COPY backend/ /app/backend/
COPY --from=frontend /app/backend/static /app/backend/static

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
