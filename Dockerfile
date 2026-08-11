FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.11-slim AS app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
RUN addgroup --system causality && adduser --system --ingroup causality causality
COPY --chown=causality:causality backend/app ./app
COPY --chown=causality:causality backend/alembic ./alembic
COPY --chown=causality:causality backend/alembic.ini ./alembic.ini
COPY --chown=causality:causality --from=frontend /frontend/dist ./static
USER causality
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
