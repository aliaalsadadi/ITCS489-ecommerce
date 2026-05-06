from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.artisans import router as artisans_router
from app.db.session import get_db
from app.models.profile import Profile
from tests.fakes import FakeAsyncSession, FakeResult


def _build_test_app(fake_db: FakeAsyncSession) -> FastAPI:
    app = FastAPI()
    app.include_router(artisans_router, prefix="/api/v1")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_artisans_returns_popularity_fields() -> None:
    artisan_id = uuid4()
    now = datetime.now(UTC)
    profile = Profile(
        id=artisan_id,
        email="artisan@example.com",
        role="artisan",
        full_name="Amina Haddad",
        shop_name="Olive Studio",
        bio="Handmade home objects.",
        profile_image_url="https://example.com/profile.jpg",
        is_suspended=False,
        created_at=now,
        updated_at=now,
    )
    fake_db = FakeAsyncSession(
        [
            FakeResult(
                [
                    (profile, 6, 19),
                ]
            )
        ]
    )
    app = _build_test_app(fake_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/artisans", params={"sort": "popular", "limit": 1})

    assert response.status_code == 200
    now_json = now.isoformat().replace("+00:00", "Z")
    assert response.json() == [
        {
            "id": str(artisan_id),
            "full_name": "Amina Haddad",
            "shop_name": "Olive Studio",
            "bio": "Handmade home objects.",
            "profile_image_url": "https://example.com/profile.jpg",
            "active_product_count": 6,
            "units_sold": 19,
            "created_at": now_json,
            "updated_at": now_json,
        }
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_artisan_returns_404_when_missing() -> None:
    fake_db = FakeAsyncSession([FakeResult([])])
    app = _build_test_app(fake_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/api/v1/artisans/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Artisan not found"}
