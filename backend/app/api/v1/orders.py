import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_profile, require_roles
from app.api.v1.admin import _log_action
from app.core.config import get_settings
from app.core.constants import AdminTargetType, OrderAction, OrderStatus, PaymentAction, UserRole
from app.db.session import get_db
from app.models.admin_action_log import AdminActionLog
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.profile import Profile
from app.schemas.order import CheckoutRequest, OrderResponse, OrderStatusUpdateRequest
from app.services.payment_simulator import simulate_payment

router = APIRouter(prefix="/orders", tags=["orders"])
settings = get_settings()

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.PENDING.value: {OrderStatus.PAID.value, OrderStatus.PROCESSING.value, OrderStatus.CANCELED.value},
    OrderStatus.PAID.value: {OrderStatus.PROCESSING.value, OrderStatus.CANCELED.value},
    OrderStatus.PROCESSING.value: {OrderStatus.SHIPPED.value, OrderStatus.CANCELED.value},
    OrderStatus.SHIPPED.value: {OrderStatus.DELIVERED.value},
    OrderStatus.DELIVERED.value: set(),
    OrderStatus.CANCELED.value: set(),
}


async def _load_customer_cart(db: AsyncSession, customer_id: uuid.UUID) -> Cart | None:
    stmt = (
        select(Cart)
        .where(Cart.customer_id == customer_id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )
    return (await db.scalars(stmt)).first()


async def _load_order(db: AsyncSession, order_id: uuid.UUID) -> Order | None:
    stmt = select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    return (await db.scalars(stmt)).first()


@router.post("/checkout", response_model=OrderResponse)
async def checkout(
    payload: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Order:
    cart = await _load_customer_cart(db, current_profile.id)
    if cart is None or not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    seed_id = uuid.uuid4()
    total_amount = Decimal("0")

    for item in cart.items:
        product = item.product
        if product is None or not product.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some products are unavailable")
        if item.quantity > product.stock_quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock for checkout")
        total_amount += product.price * Decimal(item.quantity)

    # Log payment attempt
    db.add(
        AdminActionLog(
            admin_id=None,
            action=PaymentAction.ATTEMPTED.value,
            target_type=AdminTargetType.ORDER.value,
            target_id=f"checkout-{uuid.uuid4()}",
            details={
                "customer_id": str(current_profile.id),
                "amount": str(total_amount),
                "payment_method": "card",
            },
        )
    )
    await db.commit()

    payment_result = simulate_payment(payload.card_token, total_amount, seed_id)
    if payment_result["status"] == "declined":
        # Log payment failure
        db.add(
            AdminActionLog(
                admin_id=None,
                action=PaymentAction.FAILED.value,
                target_type=AdminTargetType.ORDER.value,
                target_id=f"checkout-{uuid.uuid4()}",
                details={
                    "customer_id": str(current_profile.id),
                    "amount": str(total_amount),
                    "decline_reason": payment_result.get("reason", "Unknown"),
                },
            )
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=payment_result.get("reason", "Payment declined"),
        )
    if payment_result["status"] == "timeout":
        # Log payment timeout
        db.add(
            AdminActionLog(
                admin_id=None,
                action=PaymentAction.FAILED.value,
                target_type=AdminTargetType.ORDER.value,
                target_id=f"checkout-{uuid.uuid4()}",
                details={
                    "customer_id": str(current_profile.id),
                    "amount": str(total_amount),
                    "decline_reason": "Payment gateway timeout",
                },
            )
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=payment_result.get("reason", "Payment gateway timeout"),
        )

    order = Order(
        customer_id=current_profile.id,
        status=OrderStatus.PAID.value,
        total_amount=total_amount,
        currency=settings.default_currency,
        shipping_address=payload.shipping_address,
        payment_transaction_id=payment_result.get("transaction_id"),
    )
    db.add(order)
    await db.flush()

    for item in cart.items:
        product = item.product
        product.stock_quantity -= item.quantity
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                artist_id=product.artist_id,
                product_name=product.name,
                quantity=item.quantity,
                unit_price=product.price,
            )
        )
        await db.delete(item)

    await db.commit()

    # Log payment success
    db.add(
        AdminActionLog(
            admin_id=None,
            action=PaymentAction.SUCCEEDED.value,
            target_type=AdminTargetType.ORDER.value,
            target_id=str(order.id),
            details={
                "order_id": str(order.id),
                "customer_id": str(current_profile.id),
                "amount": str(total_amount),
                "transaction_id": payment_result.get("transaction_id"),
            },
        )
    )

    # Log order creation
    db.add(
        AdminActionLog(
            admin_id=None,
            action=OrderAction.CREATED.value,
            target_type=AdminTargetType.ORDER.value,
            target_id=str(order.id),
            details={
                "order_id": str(order.id),
                "customer_id": str(current_profile.id),
                "total_amount": str(total_amount),
                "source": "cart",
                "items_count": len(cart.items),
                "payment_transaction_id": payment_result.get("transaction_id"),
            },
        )
    )
    await db.commit()

    return await _load_order(db, order.id)


@router.get("", response_model=list[OrderResponse])
async def list_my_orders(
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.customer_id == current_profile.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return list((await db.scalars(stmt)).all())


@router.get("/artisan/sales", response_model=list[OrderResponse])
async def list_artisan_sales(
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> list[Order]:
    stmt = select(Order).join(OrderItem)
    if current_profile.role != UserRole.ADMIN.value:
        stmt = stmt.where(OrderItem.artist_id == current_profile.id)

    stmt = stmt.options(selectinload(Order.items)).order_by(Order.created_at.desc())
    return list((await db.scalars(stmt)).unique().all())


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Order:
    order = await _load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    is_owner = order.customer_id == current_profile.id
    is_admin = current_profile.role == UserRole.ADMIN.value
    is_related_artisan = any(item.artist_id == current_profile.id for item in order.items)
    if not (is_owner or is_admin or is_related_artisan):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> Order:
    order = await _load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if current_profile.role != UserRole.ADMIN.value:
        touches_artisan = any(item.artist_id == current_profile.id for item in order.items)
        if not touches_artisan:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    current_status = order.status
    next_status = payload.status.value
    if current_status != next_status:
        allowed_next = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if next_status not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current_status}' to '{next_status}'",
            )

    if payload.tracking_number is not None:
        order.tracking_number = payload.tracking_number
    if payload.shipping_carrier is not None:
        order.shipping_carrier = payload.shipping_carrier
    if payload.shipping_method is not None:
        order.shipping_method = payload.shipping_method
    if payload.estimated_delivery_at is not None:
        order.estimated_delivery_at = payload.estimated_delivery_at

    if next_status == OrderStatus.SHIPPED.value:
        if not order.tracking_number or not order.shipping_carrier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tracking number and shipping carrier are required when marking an order as shipped",
            )

    order.status = payload.status.value
    await db.commit()
    return await _load_order(db, order.id)
