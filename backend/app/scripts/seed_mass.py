from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import delete, select

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.constants import AdminTargetType, OrderAction, OrderStatus, PaymentAction, ProductAction
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.admin_action_log import AdminActionLog
from app.models.cart import Cart
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.profile import Profile

SEED_DOMAIN = "souq-demo.local"
SEED_PASSWORD = "DemoPass123!"
MASS_SEED_SOURCE = "mass_seed"
RNG = random.Random(489)

ORDER_STATUSES = (
    OrderStatus.PAID.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.DELIVERED.value,
)


@dataclass(frozen=True)
class SeedUser:
    email: str
    role: str
    full_name: str
    shop_name: str | None = None
    bio: str | None = None
    profile_image_url: str | None = None


@dataclass(frozen=True)
class CategorySeed:
    category: str
    nouns: tuple[str, ...]
    materials: tuple[str, ...]
    descriptions: tuple[str, ...]
    images: tuple[str, ...]
    price_range: tuple[int, int]


PROFILE_IMAGES = (
    "https://images.unsplash.com/photo-1452860606245-08befc0ff44b?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1519710164239-da123dc03ef4?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1518005020951-eccb494ad742?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80",
)

CATEGORY_SEEDS: tuple[CategorySeed, ...] = (
    CategorySeed(
        "pottery",
        ("vase", "tea cup set", "serving bowl", "incense holder", "planter", "pitcher"),
        ("stoneware", "speckled clay", "terracotta", "matte ceramic"),
        (
            "Thrown by hand and finished with a soft glaze for everyday rituals.",
            "A warm studio piece with small variations that make every item unique.",
            "Designed for slow mornings, shared tables, and display shelves.",
        ),
        (
            "https://images.unsplash.com/photo-1493106819501-66d381c466f1?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1610701596007-11502861dcfa?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1612196808214-b7e239e5f6a2?auto=format&fit=crop&w=900&q=80",
        ),
        (14, 72),
    ),
    CategorySeed(
        "jewelry",
        ("pendant", "bracelet", "ring", "earrings", "chain", "brooch"),
        ("sterling silver", "brass", "freshwater pearl", "hammered copper"),
        (
            "A small-batch adornment shaped, polished, and finished by hand.",
            "Minimal enough for daily wear with a craft detail that catches the light.",
            "Made for gifting, layering, and keeping close.",
        ),
        (
            "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1605100804763-247f67b3557e?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=900&q=80",
        ),
        (18, 96),
    ),
    CategorySeed(
        "textiles",
        ("throw blanket", "table runner", "woven scarf", "cushion cover", "wall hanging", "linen pouch"),
        ("cotton", "linen", "wool", "palm fiber"),
        (
            "Woven in a textured pattern that brings softness and rhythm to the room.",
            "A tactile piece made for daily use and quiet corners.",
            "Finished with careful edges and an understated natural palette.",
        ),
        (
            "https://images.unsplash.com/photo-1524758631624-e2822e304c36?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1616046229478-9901c5536a45?auto=format&fit=crop&w=900&q=80",
        ),
        (16, 85),
    ),
    CategorySeed(
        "woodwork",
        ("serving board", "keepsake box", "spice spoon", "wall shelf", "candle stand", "desk tray"),
        ("walnut", "olive wood", "oak", "reclaimed teak"),
        (
            "Sanded smooth, oil-finished, and made to show the grain clearly.",
            "A useful object with warm edges and a quiet sculptural profile.",
            "Built in small batches for homes that value natural materials.",
        ),
        (
            "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1611486212557-88be5ff6f941?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1533090481720-856c6e3c1fdc?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1517705008128-361805f42e86?auto=format&fit=crop&w=900&q=80",
        ),
        (20, 110),
    ),
    CategorySeed(
        "leather",
        ("card wallet", "journal cover", "key loop", "crossbody pouch", "tool roll", "passport sleeve"),
        ("vegetable-tanned leather", "nubuck", "saddle leather", "soft grain leather"),
        (
            "Cut, stitched, and burnished by hand for a piece that will age well.",
            "Made with clean lines, sturdy hardware, and a compact everyday shape.",
            "A durable companion designed to gather character over time.",
        ),
        (
            "https://images.unsplash.com/photo-1523779105320-d1cd346ff52b?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=900&q=80",
        ),
        (22, 130),
    ),
    CategorySeed(
        "candles",
        ("soy candle", "beeswax taper set", "ceramic candle", "travel tin", "scented votive", "wax melt set"),
        ("soy wax", "beeswax", "coconut wax", "botanical wax"),
        (
            "Poured in small batches with a clean burn and layered scent.",
            "A calm companion for reading, dining, and evening rituals.",
            "Balanced fragrance notes with a handmade vessel ready to reuse.",
        ),
        (
            "https://images.unsplash.com/photo-1603006905003-be475563bc59?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1602874801007-bd458bb1b8b6?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1602524206684-7919b2b24f95?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1607344645866-009c7d7ccf12?auto=format&fit=crop&w=900&q=80",
        ),
        (8, 42),
    ),
    CategorySeed(
        "paintings",
        ("mini canvas", "watercolor study", "abstract panel", "landscape print", "botanical painting", "ink artwork"),
        ("watercolor", "acrylic", "natural pigment", "ink"),
        (
            "An expressive piece made to bring color and movement to a wall.",
            "Painted in a small format that fits shelves, desks, and gallery clusters.",
            "A hand-finished artwork with visible brushwork and layered tone.",
        ),
        (
            "https://images.unsplash.com/photo-1541961017774-22349e4a1262?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1515405295579-ba7b45403062?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1579783901586-d88db74b4fe4?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1554907984-15263bfd63bd?auto=format&fit=crop&w=900&q=80",
        ),
        (24, 180),
    ),
    CategorySeed(
        "baskets",
        ("market basket", "storage tray", "lidded basket", "bread basket", "wall basket", "woven hamper"),
        ("date palm", "seagrass", "raffia", "rattan"),
        (
            "Woven with a sturdy structure for market days and open shelving.",
            "A practical storage piece with natural texture and handmade variation.",
            "Lightweight, durable, and shaped with traditional weaving techniques.",
        ),
        (
            "https://images.unsplash.com/photo-1598300042247-d088f8ab3a91?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1602028915047-37269d1a73f7?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1594040226829-7f251ab46d80?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1616486029423-aaa4789e8c9a?auto=format&fit=crop&w=900&q=80",
        ),
        (12, 76),
    ),
    CategorySeed(
        "glass",
        ("blown tumbler", "bud vase", "sun catcher", "glass dish", "ornament set", "table lantern"),
        ("recycled glass", "colored glass", "clear glass", "frosted glass"),
        (
            "Made in small batches with gentle color shifts and hand-finished edges.",
            "A luminous piece for windows, table settings, and gifting.",
            "Shaped to catch light and add a quiet glow to everyday spaces.",
        ),
        (
            "https://images.unsplash.com/photo-1520038410233-7141be7e6f97?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1526933053326-89d4b2f8fbee?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1618220179428-22790b461013?auto=format&fit=crop&w=900&q=80",
        ),
        (18, 118),
    ),
    CategorySeed(
        "decor",
        ("ceramic wall hook", "table sculpture", "linen banner", "door charm", "decorative bowl", "shelf object"),
        ("mixed media", "natural clay", "brass", "woven fiber"),
        (
            "A refined accent object designed to make a room feel personal.",
            "Crafted in a small studio with texture, balance, and simple utility.",
            "A versatile decor piece for gifting, styling, or daily use.",
        ),
        (
            "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1534349762230-e0cadf78f5da?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1513161455079-7dc1de15ef3e?auto=format&fit=crop&w=900&q=80",
            "https://images.unsplash.com/photo-1618220179428-22790b461013?auto=format&fit=crop&w=900&q=80",
        ),
        (10, 92),
    ),
)

SHOP_WORDS = (
    "Olive", "Palm", "Pearl", "Saffron", "Cedar", "Dune", "Indigo", "Copper", "Oasis", "Moon",
    "Clay", "Thread", "Jasmine", "Amber", "Harbor", "Mosaic", "Date", "Sun", "Terrace", "Falcon",
)
SHOP_SUFFIXES = ("Studio", "Atelier", "Workshop", "House", "Collective")
FIRST_NAMES = (
    "Amina", "Layla", "Noura", "Mariam", "Salma", "Huda", "Reem", "Dana", "Fatima", "Yasmin",
    "Omar", "Khalid", "Yusuf", "Ali", "Hassan", "Rashid", "Faisal", "Zaid", "Sami", "Tariq",
)
LAST_NAMES = (
    "Al Noor", "Haddad", "Saleh", "Mansour", "Rahman", "Karim", "Farah", "Nasser", "Bashir", "Qasim",
)
CUSTOMER_NAMES = (
    "Mona Reed", "Lina Stone", "Adam Brooks", "Sara Hill", "Noah Clark", "Hana White", "Maya Evans",
    "Zara Quinn", "Liam Gray", "Ola Mason", "Rami Wells", "Tala Green", "Nina Bell", "Kareem Fox",
    "Dina Lane", "Amal Cruz", "Mira West", "Samir King", "Nadia Ray", "Elias Cole",
)


def _money(value: int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _admin_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for mass seeding")

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
    return response.json().get("users", [])


async def _create_auth_user(client: httpx.AsyncClient, user: SeedUser) -> dict:
    settings = get_settings()
    response = await client.post(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=_admin_headers(),
        json={
            "email": user.email,
            "password": SEED_PASSWORD,
            "email_confirm": True,
            "user_metadata": {"full_name": user.full_name},
        },
    )
    response.raise_for_status()
    return response.json()


async def _get_or_create_auth_users(users: list[SeedUser]) -> dict[str, uuid.UUID]:
    settings = get_settings()
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        existing = {item.get("email", "").lower(): item for item in await _list_auth_users(client)}
        result: dict[str, uuid.UUID] = {}
        for user in users:
            auth_user = existing.get(user.email.lower())
            if auth_user is None:
                auth_user = await _create_auth_user(client, user)
                existing[user.email.lower()] = auth_user
            result[user.email] = uuid.UUID(auth_user["id"])
        return result


def _build_users() -> tuple[SeedUser, list[SeedUser], list[SeedUser]]:
    admin = SeedUser(
        email=f"admin@{SEED_DOMAIN}",
        role="admin",
        full_name="Souq Demo Admin",
        bio="Demo administrator for Souq Al Artisan.",
    )
    artisans: list[SeedUser] = []
    for index in range(20):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[index % len(LAST_NAMES)]
        shop_name = f"{SHOP_WORDS[index]} {SHOP_SUFFIXES[index % len(SHOP_SUFFIXES)]}"
        artisans.append(
            SeedUser(
                email=f"artisan{index + 1:02d}@{SEED_DOMAIN}",
                role="artisan",
                full_name=f"{first} {last}",
                shop_name=shop_name,
                bio=(
                    f"{shop_name} creates small-batch handmade pieces with careful materials, "
                    "balanced forms, and a focus on objects people can live with every day."
                ),
                profile_image_url=PROFILE_IMAGES[index % len(PROFILE_IMAGES)],
            )
        )

    customers: list[SeedUser] = []
    for index in range(40):
        name = CUSTOMER_NAMES[index % len(CUSTOMER_NAMES)]
        suffix = index // len(CUSTOMER_NAMES)
        customers.append(
            SeedUser(
                email=f"customer{index + 1:02d}@{SEED_DOMAIN}",
                role="customer",
                full_name=name if suffix == 0 else f"{name} {suffix + 1}",
            )
        )
    return admin, artisans, customers


async def _upsert_profiles(users: list[SeedUser], user_ids: dict[str, uuid.UUID]) -> None:
    async with AsyncSessionLocal() as session:
        for user in users:
            profile = await session.get(Profile, user_ids[user.email])
            if profile is None:
                profile = Profile(id=user_ids[user.email], email=user.email)
                session.add(profile)
            profile.email = user.email
            profile.role = user.role
            profile.full_name = user.full_name
            profile.shop_name = user.shop_name
            profile.bio = user.bio
            profile.profile_image_url = user.profile_image_url
            profile.is_suspended = False
        await session.commit()


async def _reset_seed_owned_rows(artisan_ids: list[uuid.UUID], customer_ids: list[uuid.UUID]) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(AdminActionLog).where(AdminActionLog.details["seed_source"].astext == MASS_SEED_SOURCE)
        )
        if customer_ids:
            await session.execute(delete(Cart).where(Cart.customer_id.in_(customer_ids)))
            await session.execute(delete(Order).where(Order.customer_id.in_(customer_ids)))
        if artisan_ids:
            await session.execute(delete(Product).where(Product.artist_id.in_(artisan_ids)))
        await session.commit()


def _product_name(category: CategorySeed, artisan_index: int, product_index: int) -> str:
    material = category.materials[(artisan_index + product_index) % len(category.materials)]
    noun = category.nouns[(artisan_index * 2 + product_index) % len(category.nouns)]
    adjective = ("Handmade", "Studio", "Textured", "Everyday", "Limited", "Heritage")[
        (artisan_index + product_index) % 6
    ]
    return f"{adjective} {material.title()} {noun.title()}"


async def _seed_products(artisans: list[SeedUser], user_ids: dict[str, uuid.UUID], admin_id: uuid.UUID) -> list[Product]:
    products: list[Product] = []
    async with AsyncSessionLocal() as session:
        for artisan_index, artisan in enumerate(artisans):
            for product_index in range(6):
                category = CATEGORY_SEEDS[(artisan_index + product_index) % len(CATEGORY_SEEDS)]
                price_min, price_max = category.price_range
                price = _money(RNG.randint(price_min, price_max) + RNG.choice((0, 0.25, 0.5, 0.75)))
                stock = RNG.randint(18, 70)
                product = Product(
                    artist_id=user_ids[artisan.email],
                    name=_product_name(category, artisan_index, product_index),
                    description=category.descriptions[(artisan_index + product_index) % len(category.descriptions)],
                    category=category.category,
                    price=price,
                    stock_quantity=stock,
                    image_url=category.images[(artisan_index + product_index) % len(category.images)],
                    is_active=True,
                )
                session.add(product)
                products.append(product)
        await session.flush()
        for product in products:
            session.add(
                AdminActionLog(
                    admin_id=admin_id,
                    action=ProductAction.CREATED.value,
                    target_type=AdminTargetType.PRODUCT.value,
                    target_id=str(product.id),
                    details={
                        "seed_source": MASS_SEED_SOURCE,
                        "name": product.name,
                        "price": str(product.price),
                        "stock_quantity": product.stock_quantity,
                        "category": product.category,
                        "artist_id": str(product.artist_id),
                    },
                )
            )
        await session.commit()
        for product in products:
            await session.refresh(product)
    return products


def _weighted_products(products: list[Product]) -> list[Product]:
    weighted: list[Product] = []
    for index, product in enumerate(products):
        if index < 12:
            weight = 9
        elif index < 36:
            weight = 5
        elif index % 7 == 0:
            weight = 4
        else:
            weight = 2
        weighted.extend([product] * weight)
    return weighted


async def _seed_orders(customers: list[SeedUser], user_ids: dict[str, uuid.UUID], products: list[Product]) -> int:
    weighted_products = _weighted_products(products)
    now = datetime.now(timezone.utc)
    orders_created = 0
    async with AsyncSessionLocal() as session:
        for index in range(220):
            customer = customers[index % len(customers)]
            status_value = ORDER_STATUSES[index % len(ORDER_STATUSES)]
            created_at = now - timedelta(days=RNG.randint(1, 110), hours=RNG.randint(0, 23), minutes=RNG.randint(0, 59))
            order = Order(
                customer_id=user_ids[customer.email],
                status=status_value,
                total_amount=Decimal("0.00"),
                currency="BHD",
                shipping_address=f"Villa {100 + index}, Road {200 + (index % 45)}, Manama, Bahrain",
                payment_transaction_id=f"seed_txn_{index + 1:04d}",
                tracking_number=f"SQ{index + 1:06d}" if status_value in {OrderStatus.SHIPPED.value, OrderStatus.DELIVERED.value} else None,
                shipping_carrier="Souq Express" if status_value in {OrderStatus.SHIPPED.value, OrderStatus.DELIVERED.value} else None,
                shipping_method="standard",
                estimated_delivery_at=created_at + timedelta(days=RNG.randint(3, 8)),
                created_at=created_at,
                updated_at=created_at + timedelta(days=RNG.randint(0, 5)),
            )
            session.add(order)
            await session.flush()

            selected: list[Product] = []
            for _ in range(RNG.randint(1, 4)):
                product = RNG.choice(weighted_products)
                if product not in selected:
                    selected.append(product)

            total = Decimal("0.00")
            item_count = 0
            for product in selected:
                quantity = RNG.randint(1, 3 if product.price < 40 else 2)
                total += product.price * Decimal(quantity)
                item_count += quantity
                product.stock_quantity = max(0, product.stock_quantity - quantity)
                session.add(
                    OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        artist_id=product.artist_id,
                        product_name=product.name,
                        quantity=quantity,
                        unit_price=product.price,
                    )
                )
            order.total_amount = total
            session.add(
                AdminActionLog(
                    admin_id=None,
                    action=PaymentAction.SUCCEEDED.value,
                    target_type=AdminTargetType.ORDER.value,
                    target_id=str(order.id),
                    details={
                        "seed_source": MASS_SEED_SOURCE,
                        "order_id": str(order.id),
                        "customer_id": str(order.customer_id),
                        "amount": str(order.total_amount),
                        "transaction_id": order.payment_transaction_id,
                    },
                    created_at=created_at,
                )
            )
            session.add(
                AdminActionLog(
                    admin_id=None,
                    action=OrderAction.CREATED.value,
                    target_type=AdminTargetType.ORDER.value,
                    target_id=str(order.id),
                    details={
                        "seed_source": MASS_SEED_SOURCE,
                        "order_id": str(order.id),
                        "customer_id": str(order.customer_id),
                        "total_amount": str(order.total_amount),
                        "source": "cart",
                        "items_count": item_count,
                        "payment_transaction_id": order.payment_transaction_id,
                    },
                    created_at=created_at,
                )
            )
            orders_created += 1

        await session.commit()
    return orders_created


async def main() -> None:
    admin, artisans, customers = _build_users()
    all_users = [admin, *artisans, *customers]

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    user_ids = await _get_or_create_auth_users(all_users)
    await _upsert_profiles(all_users, user_ids)

    artisan_ids = [user_ids[user.email] for user in artisans]
    customer_ids = [user_ids[user.email] for user in customers]
    await _reset_seed_owned_rows(artisan_ids, customer_ids)

    products = await _seed_products(artisans, user_ids, user_ids[admin.email])
    orders_created = await _seed_orders(customers, user_ids, products)

    print("Mass seed completed.")
    print(f"- admin: {admin.email}")
    print(f"- artisans: {len(artisans)}")
    print(f"- customers: {len(customers)}")
    print(f"- products: {len(products)}")
    print(f"- orders: {orders_created}")
    print(f"- admin_activity_logs: {len(products) + (orders_created * 2)}")
    print(f"- demo_password: {SEED_PASSWORD}")
    print("- rerun behavior: resets seed-owned carts, orders, products, and audit logs before recreating them")


if __name__ == "__main__":
    asyncio.run(main())
