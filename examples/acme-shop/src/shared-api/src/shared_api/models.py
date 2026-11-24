from pydantic import BaseModel


class Invoice(BaseModel):
    id: int
    customer_id: int
    total_cents: int
    currency: str
