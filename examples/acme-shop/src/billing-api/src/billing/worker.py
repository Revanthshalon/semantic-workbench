import time

from kafka import KafkaProducer

from billing import outbox
from billing.db import SessionLocal
from billing.repo import InvoiceRepo
from billing.services import process
from shared_api.models import Invoice

producer = KafkaProducer(bootstrap_servers="kafka:9092")
repo = InvoiceRepo()


def send_invoice(invoice: Invoice) -> None:
    producer.send("invoice.created", invoice.model_dump_json())


def relay_once() -> None:
    with SessionLocal() as db, db.begin():
        for event in outbox.pending(db):
            send_invoice(Invoice.model_validate_json(event.payload))
            outbox.mark_sent(db, event)
    process(repo)


def main() -> None:
    while True:
        relay_once()
        time.sleep(1)


if __name__ == "__main__":
    main()
