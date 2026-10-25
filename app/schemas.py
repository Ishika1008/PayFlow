from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=50)
    amount: float = Field(gt=0, le=100000)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=64)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: str
    customer_id: str
    amount: float
    currency: str
    status: str
    failure_reason: Optional[str]
    retry_count: int
    created_at: datetime