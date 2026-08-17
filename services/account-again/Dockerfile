FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY account_again ./account_again
COPY dualstack_start.py ./dualstack_start.py
RUN pip install --no-cache-dir .
EXPOSE 8001
ENV ACCOUNT_AGAIN_DATABASE_URL=sqlite:////data/account_again.db
ENV APP_MODULE=account_again.main:app
ENV PORT=8001
VOLUME ["/data"]
CMD ["python", "dualstack_start.py"]
