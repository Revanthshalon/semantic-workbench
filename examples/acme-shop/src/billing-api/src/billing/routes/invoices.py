from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from billing import outbox
from billing.db import get_db
from billing.models import InvoiceIn, InvoiceRow
from billing.outbox import INVOICE_CREATED
from shared_api.models import Invoice

router = APIRouter(prefix="/invoices")


@router.get("/{invoice_id}", response_model=Invoice)
async def get_invoice(invoice_id: int, db: Session = Depends(get_db)) -> Invoice:
    return Invoice.model_validate(db.get(InvoiceRow, invoice_id))


@router.post("/", response_model=Invoice, status_code=201)
async def create_invoice(body: InvoiceIn, db: Session = Depends(get_db)) -> Invoice:
    with db.begin():
        row = InvoiceRow(**body.model_dump())
        db.add(row)
        db.flush()
        invoice = Invoice.model_validate(row)
        outbox.record(db, INVOICE_CREATED, invoice)
    return invoice
