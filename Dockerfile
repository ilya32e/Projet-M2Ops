FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY sources.csv ./sources.csv

RUN pip install --no-cache-dir --no-deps . \
    && addgroup --system gazette \
    && adduser --system --ingroup gazette gazette \
    && mkdir -p /app/data \
    && chown -R gazette:gazette /app

USER gazette

ENTRYPOINT ["python", "-m", "gazette.cli"]
CMD ["--source", "Le Monde", "--output", "/app/data/items.jsonl"]
