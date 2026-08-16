# Document Again — production image (built from OIODA monorepo root).
FROM python:3.12-slim

WORKDIR /app

COPY services/document-again/backend/requirements.txt requirements.txt 2>/dev/null || true
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || pip install --no-cache-dir fastapi uvicorn sqlalchemy httpx python-dotenv

COPY services/document-again/backend /app

ENV AUTH_MODE=ecosystem
EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
