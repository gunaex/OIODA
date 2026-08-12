# Account Again — local/development container image.
# NOT build-verified in this session (see docs/current-state/E5_DEPLOYMENT_READINESS.md
# in AGAIN-ECOSYSTEM) — authored as a topology artifact per E5 task §50, reviewed for
# correctness against pyproject.toml, not run through `docker build`.
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY account_again ./account_again
COPY alembic ./alembic

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8001
ENV ACCOUNT_AGAIN_DATABASE_URL=sqlite:////data/account_again.db
VOLUME ["/data"]

CMD ["uvicorn", "account_again.main:app", "--host", "0.0.0.0", "--port", "8001"]
