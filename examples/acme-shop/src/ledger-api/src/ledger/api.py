from fastapi import FastAPI
from pydantic import BaseModel

from ledger.clients import fetch_invoice

app = FastAPI()


class EntryIn(BaseModel):
    invoice_id: int


@app.post("/entries")
def add_entry(entry: EntryIn):
    invoice = fetch_invoice(entry.invoice_id)
    ...
