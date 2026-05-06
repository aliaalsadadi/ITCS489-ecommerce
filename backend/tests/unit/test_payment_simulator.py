from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.deps import require_roles
from app.core.constants import UserRole
from app.models.profile import Profile
from app.services.payment_simulator import simulate_payment


@pytest.mark.unit
def test_simulate_payment_accepts_demo_card() -> None:
    result = simulate_payment("1111222233334444", Decimal("42.50"), uuid4())

    assert result["status"] == "success"
    assert "transaction_id" in result


@pytest.mark.unit
def test_simulate_payment_declines_non_demo_card() -> None:
    result = simulate_payment("4000000000000000", Decimal("42.50"), uuid4())

    assert result == {
        "status": "declined",
        "reason": "This card is not accepted. Use 1111222233334444 for demo purposes.",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_roles_rejects_wrong_role() -> None:
    guard = require_roles(UserRole.ADMIN)
    profile = Profile(role=UserRole.CUSTOMER.value)

    with pytest.raises(HTTPException) as exc_info:
        await guard(current_profile=profile)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Permission denied"
