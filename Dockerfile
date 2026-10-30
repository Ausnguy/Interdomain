# One image for every Python process (API, producer, consumer, maintenance,
# migrations). Compose picks the process with `command:`.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
COPY scripts ./scripts
COPY sql ./sql

# Do not run as root inside the container.
RUN useradd --system --no-create-home app
USER app

CMD ["uvicorn", "interdomain.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
