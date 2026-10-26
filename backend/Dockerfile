FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/data ./data
COPY backend/scripts ./scripts
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY evaluation_module/__init__.py /app/evaluation_module/__init__.py
COPY evaluation_module/mudra_mlp /app/evaluation_module/mudra_mlp
COPY evaluation_module/sequence /app/evaluation_module/sequence
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
