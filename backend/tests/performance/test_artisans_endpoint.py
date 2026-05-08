from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.artisans import router as artisans_router
from app.db.session import get_db
from app.models.profile import Profile
from tests.fakes import FakeAsyncSession, FakeResult


def _build_perf_app() -> FastAPI:
    now = datetime.now(UTC)
    profiles = []
    for index in range(12):
        profiles.append(
            (
                Profile(
                    id=uuid4(),
                    email=f"artisan{index}@example.com",
                    role="artisan",
                    full_name=f"Artisan {index}",
                    shop_name=f"Studio {index}",
                    bio="Performance test artisan profile.",
                    profile_image_url=None,
                    is_suspended=False,
                    created_at=now,
                    updated_at=now,
                ),
                6 + index,
                30 - index,
            )
        )

    fake_db = FakeAsyncSession([FakeResult(profiles) for _ in range(80)])
    app = FastAPI()
    app.include_router(artisans_router, prefix="/api/v1")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.mark.performance
@pytest.mark.asyncio
async def test_artisans_endpoint_average_latency_under_50ms() -> None:
    app = _build_perf_app()
    samples: list[float] = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        for _ in range(80):
            started = perf_counter()
            response = await client.get("/api/v1/artisans", params={"sort": "popular", "limit": 12})
            elapsed = perf_counter() - started
            assert response.status_code == 200
            samples.append(elapsed)

    average_ms = sum(samples) / len(samples) * 1000
    p95_ms = sorted(samples)[int(len(samples) * 0.95) - 1] * 1000
    print(f"Average latency: {average_ms:.2f}ms")
    print(f"P95 latency: {p95_ms:.2f}ms")
    assert average_ms < 50, f"Average latency was {average_ms:.2f}ms"
    assert p95_ms < 75, f"P95 latency was {p95_ms:.2f}ms"
