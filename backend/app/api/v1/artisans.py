import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import OrderStatus, UserRole
from app.db.session import get_db
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.profile import Profile
from app.schemas.artisan import ArtisanDetailResponse, ArtisanSummaryResponse
from app.schemas.product import ProductResponse

router = APIRouter(prefix="/artisans", tags=["artisans"])
POPULAR_ORDER_STATUSES = (
    OrderStatus.PAID.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.DELIVERED.value,
)


def _active_product_count_subquery():
    return (
        select(
            Product.artist_id.label("artist_id"),
            func.count(Product.id).label("active_product_count"),
        )
        .where(Product.is_active.is_(True))
        .group_by(Product.artist_id)
        .subquery()
    )


def _artisan_units_sold_subquery():
    return (
        select(
            OrderItem.artist_id.label("artist_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.status.in_(POPULAR_ORDER_STATUSES), OrderItem.artist_id.is_not(None))
        .group_by(OrderItem.artist_id)
        .subquery()
    )


def _product_units_sold_subquery():
    return (
        select(
            OrderItem.product_id.label("product_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.status.in_(POPULAR_ORDER_STATUSES), OrderItem.product_id.is_not(None))
        .group_by(OrderItem.product_id)
        .subquery()
    )


def _artisan_summary(profile: Profile, active_product_count: int | None, units_sold: int | None) -> ArtisanSummaryResponse:
    return ArtisanSummaryResponse(
        id=profile.id,
        full_name=profile.full_name,
        shop_name=profile.shop_name,
        bio=profile.bio,
        profile_image_url=profile.profile_image_url,
        active_product_count=int(active_product_count or 0),
        units_sold=int(units_sold or 0),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _product_response(product: Product, profile: Profile, units_sold: int | None) -> ProductResponse:
    return ProductResponse.model_validate(product).model_copy(
        update={
            "artist_name": profile.full_name,
            "artist_shop_name": profile.shop_name,
            "artist_profile_image_url": profile.profile_image_url,
            "units_sold": int(units_sold or 0),
        }
    )


@router.get("", response_model=list[ArtisanSummaryResponse])
async def list_artisans(
    sort: Literal["popular", "newest"] = Query(default="popular"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ArtisanSummaryResponse]:
    active_products = _active_product_count_subquery()
    units_sold = _artisan_units_sold_subquery()
    active_count_expr = func.coalesce(active_products.c.active_product_count, 0)
    units_sold_expr = func.coalesce(units_sold.c.units_sold, 0)

    stmt = (
        select(Profile, active_count_expr.label("active_product_count"), units_sold_expr.label("units_sold"))
        .outerjoin(active_products, Profile.id == active_products.c.artist_id)
        .outerjoin(units_sold, Profile.id == units_sold.c.artist_id)
        .where(Profile.role == UserRole.ARTISAN.value, Profile.is_suspended.is_(False))
    )
    if sort == "popular":
        stmt = stmt.order_by(units_sold_expr.desc(), active_count_expr.desc(), Profile.created_at.desc())
    else:
        stmt = stmt.order_by(Profile.created_at.desc())

    rows = (await db.execute(stmt.offset(offset).limit(limit))).all()
    return [_artisan_summary(profile, active_product_count, units_sold_value) for profile, active_product_count, units_sold_value in rows]


@router.get("/{artisan_id}", response_model=ArtisanDetailResponse)
async def get_artisan(artisan_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ArtisanDetailResponse:
    active_products = _active_product_count_subquery()
    units_sold = _artisan_units_sold_subquery()
    active_count_expr = func.coalesce(active_products.c.active_product_count, 0)
    units_sold_expr = func.coalesce(units_sold.c.units_sold, 0)

    stmt = (
        select(Profile, active_count_expr.label("active_product_count"), units_sold_expr.label("units_sold"))
        .outerjoin(active_products, Profile.id == active_products.c.artist_id)
        .outerjoin(units_sold, Profile.id == units_sold.c.artist_id)
        .where(
            Profile.id == artisan_id,
            Profile.role == UserRole.ARTISAN.value,
            Profile.is_suspended.is_(False),
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan not found")

    profile, active_product_count, units_sold_value = row
    product_units = _product_units_sold_subquery()
    products_stmt = (
        select(Product, func.coalesce(product_units.c.units_sold, 0).label("units_sold"))
        .outerjoin(product_units, Product.id == product_units.c.product_id)
        .where(Product.artist_id == profile.id, Product.is_active.is_(True))
        .order_by(func.coalesce(product_units.c.units_sold, 0).desc(), Product.created_at.desc())
        .limit(100)
    )
    product_rows = (await db.execute(products_stmt)).all()
    products = [_product_response(product, profile, product_units_sold) for product, product_units_sold in product_rows]

    summary = _artisan_summary(profile, active_product_count, units_sold_value)
    return ArtisanDetailResponse(**summary.model_dump(), products=products)
