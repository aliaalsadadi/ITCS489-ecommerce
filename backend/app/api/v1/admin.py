from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_roles
from app.core.constants import AdminTargetType, AuctionStatus, OrderStatus, UserRole
from app.db.session import get_db
from app.models.admin_action_log import AdminActionLog
from app.models.auction import Auction
from app.models.order import Order
from app.models.product import Product
from app.models.profile import Profile
from app.schemas.admin import (
    AdminActionLogResponse,
    AdminAuctionStatusRequest,
    AdminDashboardSummary,
    AdminOrderStatusRequest,
    AdminProductModerationRequest,
    AdminUserResponse,
    AdminUserRoleUpdateRequest,
    AdminUserSuspensionRequest,
)
from app.schemas.auction import AuctionStatusResponse
from app.schemas.order import OrderResponse
from app.schemas.product import ProductResponse
from app.services.auction_service import close_auction

router = APIRouter(prefix="/admin", tags=["admin"])


async def _log_action(
    db: AsyncSession,
    admin_id: uuid.UUID,
    action: str,
    target_type: AdminTargetType,
    target_id: str,
    details: dict,
) -> None:
    db.add(
        AdminActionLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type.value,
            target_id=target_id,
            details=details,
        )
    )


@router.get("/dashboard", response_model=AdminDashboardSummary)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> AdminDashboardSummary:
    users_total = (await db.execute(select(func.count()).select_from(Profile))).scalar_one()
    users_suspended = (
        await db.execute(select(func.count()).select_from(Profile).where(Profile.is_suspended.is_(True)))
    ).scalar_one()
    products_total = (await db.execute(select(func.count()).select_from(Product))).scalar_one()
    orders_total = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    auctions_total = (await db.execute(select(func.count()).select_from(Auction))).scalar_one()
    revenue_total = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.status.in_([OrderStatus.PAID.value, OrderStatus.PROCESSING.value, OrderStatus.SHIPPED.value])
            )
        )
    ).scalar_one()

    return AdminDashboardSummary(
        users_total=users_total,
        users_suspended=users_suspended,
        products_total=products_total,
        orders_total=orders_total,
        auctions_total=auctions_total,
        revenue_total=str(Decimal(revenue_total)),
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    role: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> list[Profile]:
    stmt: Select[tuple[Profile]] = select(Profile)
    if role:
        stmt = stmt.where(Profile.role == role)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Profile.email.ilike(pattern))

    stmt = stmt.order_by(Profile.created_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
async def set_user_role(
    user_id: uuid.UUID,
    payload: AdminUserRoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> Profile:
    target = await db.get(Profile, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = target.role
    target.role = payload.role.value
    await _log_action(
        db,
        admin.id,
        "set_user_role",
        AdminTargetType.USER,
        str(target.id),
        {"old_role": old_role, "new_role": target.role},
    )
    await db.commit()
    await db.refresh(target)
    return target


@router.patch("/users/{user_id}/suspension", response_model=AdminUserResponse)
async def set_user_suspension(
    user_id: uuid.UUID,
    payload: AdminUserSuspensionRequest,
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> Profile:
    target = await db.get(Profile, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.is_suspended = payload.is_suspended
    await _log_action(
        db,
        admin.id,
        "set_user_suspension",
        AdminTargetType.USER,
        str(target.id),
        {"is_suspended": payload.is_suspended},
    )
    await db.commit()
    await db.refresh(target)
    return target


@router.get("/products", response_model=list[ProductResponse])
async def list_products_admin(
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> list[Product]:
    stmt = select(Product).order_by(Product.created_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def moderate_product(
    product_id: uuid.UUID,
    payload: AdminProductModerationRequest,
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    old_value = product.is_active
    product.is_active = payload.is_active
    await _log_action(
        db,
        admin.id,
        "moderate_product",
        AdminTargetType.PRODUCT,
        str(product.id),
        {"old_is_active": old_value, "new_is_active": payload.is_active},
    )
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders_admin(
    status_filter: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> list[Order]:
    stmt: Select[tuple[Order]] = select(Order).options(selectinload(Order.items))
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def set_order_status_admin(
    order_id: uuid.UUID,
    payload: AdminOrderStatusRequest,
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> Order:
    stmt = select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    order = (await db.scalars(stmt)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    old_status = order.status
    order.status = payload.status.value
    await _log_action(
        db,
        admin.id,
        "set_order_status",
        AdminTargetType.ORDER,
        str(order.id),
        {"old_status": old_status, "new_status": order.status},
    )
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/auctions", response_model=list[AuctionStatusResponse])
async def list_auctions_admin(
    status_filter: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> list[Auction]:
    stmt: Select[tuple[Auction]] = select(Auction)
    if status_filter:
        stmt = stmt.where(Auction.status == status_filter)
    stmt = stmt.order_by(Auction.created_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.patch("/auctions/{auction_id}/status", response_model=AuctionStatusResponse)
async def set_auction_status_admin(
    auction_id: uuid.UUID,
    payload: AdminAuctionStatusRequest,
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> Auction:
    auction = await db.get(Auction, auction_id)
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")

    if payload.status == AuctionStatus.CLOSED:
        auction = await close_auction(db, auction.id, closed_by=admin)
    elif payload.status == AuctionStatus.CANCELED:
        auction.status = AuctionStatus.CANCELED.value
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only closed/canceled allowed")

    await _log_action(
        db,
        admin.id,
        "set_auction_status",
        AdminTargetType.AUCTION,
        str(auction.id),
        {"new_status": auction.status},
    )
    await db.commit()
    await db.refresh(auction)
    return auction


@router.get("/audit-logs", response_model=list[AdminActionLogResponse])
async def list_audit_logs(
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: Profile = Depends(require_roles(UserRole.ADMIN)),
) -> list[AdminActionLog]:
    stmt: Select[tuple[AdminActionLog]] = select(AdminActionLog)
    if action:
        stmt = stmt.where(AdminActionLog.action == action)
    if target_type:
        stmt = stmt.where(AdminActionLog.target_type == target_type)
    stmt = stmt.order_by(AdminActionLog.created_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(stmt)).all())
