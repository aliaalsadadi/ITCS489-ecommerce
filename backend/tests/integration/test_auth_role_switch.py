from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_profile
from app.api.v1.auth import router as auth_router
from app.db.session import get_db
from app.models.profile import Profile


class FakeCommitSession:
    async def commit(self) -> None:  # pragma: no cover
        return None

    async def refresh(self, instance: object) -> None:  # pragma: no cover
        return None


def _build_test_app(*, fake_db: FakeCommitSession, profile: Profile) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")

    async def _override_get_db():
        yield fake_db

    async def _override_get_current_profile():
        return profile

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_profile] = _override_get_current_profile
    return app


def _profile_with_role(role: str) -> Profile:
    now = datetime.now(UTC)
    return Profile(
        id=uuid4(),
        email="buyer@example.com",
        role=role,
        full_name="Buyer",
        shop_name=None,
        bio=None,
        profile_image_url=None,
        wallet_balance=Decimal("0"),
        is_suspended=False,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_customer_can_switch_to_artisan() -> None:
    profile = _profile_with_role("customer")
    app = _build_test_app(fake_db=FakeCommitSession(), profile=profile)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/v1/auth/me/role", json={"role": "artisan"})

    assert response.status_code == 200
    assert response.json()["role"] == "artisan"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_customer_cannot_switch_to_admin() -> None:
    profile = _profile_with_role("customer")
    app = _build_test_app(fake_db=FakeCommitSession(), profile=profile)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/v1/auth/me/role", json={"role": "admin"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_artisan_cannot_switch_back_to_customer() -> None:
    profile = _profile_with_role("artisan")
    app = _build_test_app(fake_db=FakeCommitSession(), profile=profile)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/v1/auth/me/role", json={"role": "customer"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied"}
