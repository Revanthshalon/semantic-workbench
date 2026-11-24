# billing-api/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY . .
RUN pip install .

FROM base AS api
CMD ["uvicorn", "billing.api:app", "--host", "0.0.0.0"]

FROM base AS worker
CMD ["python", "-m", "billing.worker"]
