import pytest

from billing.repo import InvoiceRepo


@pytest.fixture
def repo():
    return InvoiceRepo()
