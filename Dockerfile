FROM python:3.12-slim AS builder

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m venv "$VIRTUAL_ENV" \
    && pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY sources.csv ./sources.csv
COPY migrations ./migrations

RUN addgroup --system gazette \
    && adduser --system --ingroup gazette gazette \
    && mkdir -p /app/data \
    && chown -R gazette:gazette /app /opt/venv

USER gazette

ENTRYPOINT ["python", "-m", "gazette.collector"]
CMD ["--interval", "1800"]
