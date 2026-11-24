from fastapi import FastAPI

from billing.routes import invoices

app = FastAPI()
app.include_router(invoices.router, prefix="/v1")
