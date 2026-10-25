import random
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import Transaction
from .schemas import TransactionCreate, TransactionOut

router = APIRouter()

FAILURE_REASONS = ["insufficient_funds", "card_declined", "network_timeout", "fraud_suspected"]
MAX_RETRIES = 3


def simulate_payment(txn: Transaction) -> None:
    """Pretend to process a payment: ~80% succeed, ~20% fail."""
    if random.random() < 0.8:
        txn.status = "success"
        txn.failure_reason = None
    else:
        txn.status = "failed"
        txn.failure_reason = random.choice(FAILURE_REASONS)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    # Duplicate protection: same key means same request, return the original
    if payload.idempotency_key:
        existing = db.scalar(
            select(Transaction).where(Transaction.idempotency_key == payload.idempotency_key)
        )
        if existing:
            return existing

    txn = Transaction(**payload.model_dump())
    simulate_payment(txn)
    db.add(txn)
    try:
        db.commit()
    except IntegrityError:
        # Two identical requests raced; the unique constraint caught the loser
        db.rollback()
        existing = db.scalar(
            select(Transaction).where(Transaction.idempotency_key == payload.idempotency_key)
        )
        if existing:
            return existing
        raise
    db.refresh(txn)
    return txn


@router.get("/transactions", response_model=List[TransactionOut])
def list_transactions(
    status: Optional[str] = Query(default=None, pattern="^(pending|success|failed)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Transaction).order_by(Transaction.created_at.desc())
    if status:
        stmt = stmt.where(Transaction.status == status)
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@router.get("/transactions/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.post("/transactions/{transaction_id}/retry", response_model=TransactionOut)
def retry_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed transactions can be retried")
    if txn.retry_count >= MAX_RETRIES:
        raise HTTPException(status_code=409, detail="Maximum retry attempts reached")

    txn.retry_count += 1
    simulate_payment(txn)
    db.commit()
    db.refresh(txn)
    return txn