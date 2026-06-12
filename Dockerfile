# ── IoT Data Interpreter Agent — container image ─────────────────────
# One container runs everything: the FastAPI backend ALSO serves the
# dashboard, so there is no separate web server to manage.

FROM python:3.11-slim

# Predictable, log-friendly Python in containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Dependencies first (cached layer — only re-installs if requirements change).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2) Application code.
COPY backend ./backend
COPY frontend ./frontend
COPY evaluation ./evaluation
COPY data ./data

# The app listens on 8000 inside the container.
EXPOSE 8000

# Container-level health: hits the API's /api/health (no extra tools needed).
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

# Bind 0.0.0.0 so the mapped port is reachable from your host machine.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
