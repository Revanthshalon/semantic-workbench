from pydantic import BaseModel
from sqlalchemy import Column, Integer, String

from billing.db import Base


class InvoiceRow(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer)
    total_cents = Column(Integer)
    currency = Column(String)


class InvoiceIn(BaseModel):
    customer_id: int
    total_cents: int
    currency: str
