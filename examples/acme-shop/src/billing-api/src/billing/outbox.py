from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session

from billing.db import Base
from shared_api.models import Invoice

INVOICE_CREATED = "invoice.created"


class OutboxEvent(Base):
    __tablename__ = "outbox"
    id = Column(Integer, primary_key=True)
    topic = Column(String)
    payload = Column(Text)
    sent_at = Column(DateTime, nullable=True)


def record(db: Session, topic: str, invoice: Invoice) -> None:
    db.add(OutboxEvent(topic=topic, payload=invoice.model_dump_json()))


def pending(db: Session, limit: int = 100) -> list[OutboxEvent]:
    return db.query(OutboxEvent).filter(OutboxEvent.sent_at.is_(None)).limit(limit).all()


def mark_sent(db: Session, event: OutboxEvent) -> None:
    event.sent_at = datetime.now(UTC)
