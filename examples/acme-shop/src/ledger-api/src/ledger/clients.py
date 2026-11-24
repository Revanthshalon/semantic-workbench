import httpx

from shared_api.models import Invoice

BILLING_URL = "http://api:8000"


def fetch_invoice(invoice_id: int) -> Invoice:
    return Invoice.model_validate(httpx.get(f"{BILLING_URL}/v1/invoices/{invoice_id}").json())
