FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /app
COPY dualstack_start.py ./dualstack_start.py
EXPOSE 8003
ENV AUTH_MODE=ecosystem
ENV DATABASE_URL=sqlite:////data/document-again.db
ENV APP_MODULE=app.main:app
ENV PORT=8003
VOLUME ["/data"]
CMD ["python", "dualstack_start.py"]
