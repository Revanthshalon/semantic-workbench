# ledger-api/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install .
CMD ["uvicorn", "ledger.api:app", "--host", "0.0.0.0"]
