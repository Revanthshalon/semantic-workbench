from billing.repo import InvoiceRepo
from billing.services import process


def test_process():
    process(InvoiceRepo())
