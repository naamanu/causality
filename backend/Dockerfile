# Causality backend — FastAPI + Anthropic hypothesis pipeline.
FROM python:3.11-slim

# Keep Python lean and unbuffered so logs stream straight to `docker compose`.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so the layer caches across source edits.
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN addgroup --system causality && adduser --system --ingroup causality causality
COPY --chown=causality:causality app ./app
USER causality

EXPOSE 8000

# 0.0.0.0 so the port is reachable from the host / other containers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
