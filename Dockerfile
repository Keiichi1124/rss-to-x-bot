FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --only main --no-root

COPY bot/ bot/
COPY .env.example .env.example
RUN mkdir -p data

EXPOSE 8080

CMD ["python", "bot/scheduler.py", "loop"]
