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
COPY config ./config

RUN addgroup --system gazette \
    && adduser --system --uid 50000 --ingroup gazette gazette \
    && mkdir -p /app/data /app/rapports \
    && chown gazette:gazette /app /app/data /app/rapports
# Pas de chown sur /opt/venv : les bibliothèques n'ont besoin que d'être lisibles, et un
# chown récursif recopierait tout l'environnement dans une couche de plus (taille x 2).

USER gazette

ENTRYPOINT ["python", "-m", "gazette.pipeline"]
CMD ["--interval", "1800"]
