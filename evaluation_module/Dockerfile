FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY evaluation_module/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY evaluation_module ./evaluation_module
COPY backend/data/seed ./backend/data/seed

CMD ["python", "-m", "evaluation_module.data_prep.validate_dataset", "--help"]
