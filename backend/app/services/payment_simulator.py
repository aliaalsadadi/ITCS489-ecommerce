import hashlib
from decimal import Decimal
from uuid import UUID, uuid4


def _deterministic_bucket(seed_text: str) -> int:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def simulate_payment(card_token: str, amount: Decimal, order_seed: UUID) -> dict:
    token = card_token.strip().lower()

    if token.startswith("success_"):
        return {"status": "success", "transaction_id": str(uuid4())}
    if token.startswith("decline_"):
        return {"status": "declined", "reason": "Card declined"}
    if token.startswith("timeout_"):
        return {"status": "timeout", "reason": "Gateway timeout"}

    bucket = _deterministic_bucket(f"{token}:{amount}:{order_seed}")
    if bucket < 90:
        return {"status": "success", "transaction_id": str(uuid4())}
    if bucket < 98:
        return {"status": "declined", "reason": "Insufficient funds"}
    return {"status": "timeout", "reason": "Gateway timeout"}
