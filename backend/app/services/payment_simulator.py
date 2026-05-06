import hashlib
from decimal import Decimal
from uuid import UUID, uuid4


def _deterministic_bucket(seed_text: str) -> int:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def simulate_payment(card_token: str, amount: Decimal, order_seed: UUID) -> dict:
    """
    Payment simulator that accepts only the demo card number 1111222233334444.
    All other cards are deterministically rejected.
    """
    token = card_token.strip().lower()

    # Only accept the demo card number
    if token == "1111222233334444":
        return {"status": "success", "transaction_id": str(uuid4())}

    # All other cards are declined
    return {
        "status": "declined",
        "reason": "This card is not accepted. Use 1111222233334444 for demo purposes.",
    }
