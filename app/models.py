import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transaction_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)