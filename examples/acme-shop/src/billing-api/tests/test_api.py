from fastapi.testclient import TestClient

from billing.api import app


def test_get_invoice(repo):
    assert TestClient(app).get("/v1/invoices/1").status_code == 200
