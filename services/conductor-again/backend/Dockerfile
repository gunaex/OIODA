# Conductor Again Backend
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY dualstack_start.py ./dualstack_start.py

EXPOSE 8000

ENV APP_MODULE=app.main:app
ENV PORT=8000

CMD ["python", "dualstack_start.py"]
