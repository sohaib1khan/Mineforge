# syntax=docker/dockerfile:1
# Multi-stage: SPA build, tests, then Python runtime serving API + static files.

# ── Frontend deps ────────────────────────────────────────────────────────────
FROM node:26-alpine AS frontend-deps
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# ── Frontend unit tests ──────────────────────────────────────────────────────
FROM frontend-deps AS frontend-test
COPY frontend/ ./
RUN npm run lint && npm run typecheck && npm run test && npm run build

# ── Frontend production build ────────────────────────────────────────────────
FROM frontend-deps AS frontend-build
COPY frontend/ ./
RUN npm run build

# ── Backend base ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS backend-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml ./backend/
COPY backend/app ./backend/app
COPY backend/migrations ./backend/migrations
COPY backend/alembic.ini ./backend/alembic.ini

# ── Backend tests ────────────────────────────────────────────────────────────
FROM backend-base AS backend-test
COPY backend/tests ./backend/tests
RUN pip install --no-cache-dir "./backend[dev]"
WORKDIR /app/backend
CMD ["pytest", "-q", "--cov=app/services", "--cov-report=term-missing", "--cov-fail-under=80"]

# ── Runtime image ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MINEFORGE_STATIC_DIR=/app/static \
    MINEFORGE_APP_DATA_DIR=/app-data

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app-data /data \
    && chown appuser:appuser /app-data /data

COPY backend/pyproject.toml ./backend/
COPY backend/app ./backend/app
COPY backend/migrations ./backend/migrations
COPY backend/alembic.ini ./backend/alembic.ini
RUN pip install --no-cache-dir ./backend \
    && chown -R appuser:appuser /app

COPY --from=frontend-build /build/dist /app/static

USER appuser
EXPOSE 8080
WORKDIR /app/backend
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
