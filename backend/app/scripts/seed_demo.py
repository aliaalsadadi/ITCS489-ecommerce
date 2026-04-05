from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal

import httpx
from sqlalchemy import func, select

import app.models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.product import Product
from app.models.profile import Profile


@dataclass(frozen=True)
class DemoUser:
    email: str
    password: str
    role: str
    full_name: str
    shop_name: str | None = None


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(
        email="admin@artisan-demo.local",
        password="DemoPass123!",
        role="admin",
        full_name="Demo Admin",
    ),
    DemoUser(
        email="artisan@artisan-demo.local",
        password="DemoPass123!",
        role="artisan",
        full_name="Demo Artisan",
        shop_name="Olive Grove Studio",
    ),
    DemoUser(
        email="customer@artisan-demo.local",
        password="DemoPass123!",
        role="customer",
        full_name="Demo Customer",
    ),
)

DEMO_PRODUCTS = (
    {
        "name": "Handwoven Palm Basket",
        "description": "Natural palm basket woven by hand for home decor.",
        "category": "textiles",
        "price": Decimal("18.00"),
        "stock_quantity": 20,
        "image_url": None,
    },
    {
        "name": "Ceramic Tea Cup Set",
        "description": "Three-piece ceramic cup set with matte glaze.",
        "category": "pottery",
        "price": Decimal("34.50"),
        "stock_quantity": 12,
        "image_url": None,
    },
    {
        "name": "Geometric Silver Pendant",
        "description": "Minimal handmade silver pendant necklace.",
        "category": "jewelry",
        "price": Decimal("42.00"),
        "stock_quantity": 15,
        "image_url": None,
    },
)


def _admin_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for demo seeding")

    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def _list_auth_users(client: httpx.AsyncClient) -> list[dict]:
    settings = get_settings()
    response = await client.get(
        f"{settings.supabase_url}/auth/v1/admin/users",
        params={"page": 1, "per_page": 1000},
        headers=_admin_headers(),
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("users", [])


async def _create_auth_user(client: httpx.AsyncClient, user: DemoUser) -> dict:
    settings = get_settings()
    response = await client.post(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=_admin_headers(),
        json={
            "email": user.email,
            "password": user.password,
            "email_confirm": True,
            "user_metadata": {"full_name": user.full_name},
        },
    )
    response.raise_for_status()
    return response.json()


async def _get_or_create_auth_user(client: httpx.AsyncClient, user: DemoUser) -> dict:
    users = await _list_auth_users(client)
    for existing in users:
        if existing.get("email", "").lower() == user.email.lower():
            return existing
    return await _create_auth_user(client, user)


async def _upsert_profile(auth_user: dict, spec: DemoUser) -> Profile:
    user_id = uuid.UUID(auth_user["id"])

    async with AsyncSessionLocal() as session:
        profile = await session.get(Profile, user_id)
        if profile is None:
            profile = Profile(id=user_id, email=spec.email)
            session.add(profile)

        profile.email = spec.email
        profile.role = spec.role
        profile.full_name = spec.full_name
        profile.shop_name = spec.shop_name
        if spec.role == "artisan" and not profile.bio:
            profile.bio = "Demo artisan profile"

        await session.commit()
        await session.refresh(profile)
        return profile


async def _seed_products_for_artisan(artisan_profile: Profile) -> int:
    async with AsyncSessionLocal() as session:
        stmt = select(func.count()).select_from(Product).where(Product.artist_id == artisan_profile.id)
        existing_count = (await session.execute(stmt)).scalar_one()
        if existing_count > 0:
            return 0

        for item in DEMO_PRODUCTS:
            session.add(Product(artist_id=artisan_profile.id, **item))

        await session.commit()
        return len(DEMO_PRODUCTS)


async def _get_artisan_products(artisan_profile: Profile) -> list[Product]:
    async with AsyncSessionLocal() as session:
        stmt = select(Product).where(Product.artist_id == artisan_profile.id).order_by(Product.created_at.asc())
        return list((await session.scalars(stmt)).all())


async def main() -> None:
    settings = get_settings()

    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    created_or_found: list[tuple[DemoUser, dict, Profile]] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for spec in DEMO_USERS:
            auth_user = await _get_or_create_auth_user(client, spec)
            profile = await _upsert_profile(auth_user, spec)
            created_or_found.append((spec, auth_user, profile))

    artisan_profile = next(profile for spec, _, profile in created_or_found if spec.role == "artisan")
    products_added = await _seed_products_for_artisan(artisan_profile)
    artisan_products = await _get_artisan_products(artisan_profile)

    print("Demo seed completed.")
    for spec, auth_user, _ in created_or_found:
        print(f"- {spec.role}: {spec.email} (id={auth_user['id']})")
    print(f"- products_added: {products_added}")
    print("- artisan_product_ids:")
    for product in artisan_products:
        print(f"  - {product.id} ({product.name})")
    print("- demo_password: DemoPass123!")


if __name__ == "__main__":
    asyncio.run(main())
