import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_profile
from app.core.config import get_settings
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.profile import Profile
from app.schemas.cart import CartItemCreateRequest, CartItemResponse, CartItemUpdateRequest, CartResponse

router = APIRouter(prefix="/cart", tags=["cart"])
settings = get_settings()


def _line_total(item: CartItem) -> Decimal:
    return item.unit_price * Decimal(item.quantity)


def _to_cart_response(cart: Cart) -> CartResponse:
    items = [
        CartItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name if item.product else "Unknown",
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=_line_total(item),
        )
        for item in cart.items
    ]
    subtotal = sum((item.line_total for item in items), Decimal("0"))
    return CartResponse(
        id=cart.id,
        customer_id=cart.customer_id,
        currency=settings.default_currency,
        items=items,
        subtotal=subtotal,
    )


async def _load_cart(db: AsyncSession, customer_id: uuid.UUID) -> Cart | None:
    stmt = (
        select(Cart)
        .where(Cart.customer_id == customer_id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )
    return (await db.scalars(stmt)).first()


async def _get_or_create_cart(db: AsyncSession, customer_id: uuid.UUID) -> Cart:
    cart = await _load_cart(db, customer_id)
    if cart is not None:
        return cart

    cart = Cart(customer_id=customer_id)
    db.add(cart)
    await db.commit()
    return await _load_cart(db, customer_id)


@router.get("", response_model=CartResponse)
async def get_cart(
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> CartResponse:
    cart = await _get_or_create_cart(db, current_profile.id)
    return _to_cart_response(cart)


@router.post("/items", response_model=CartResponse)
async def add_cart_item(
    payload: CartItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> CartResponse:
    product = await db.get(Product, payload.product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    cart = await _get_or_create_cart(db, current_profile.id)

    existing = next((item for item in cart.items if item.product_id == payload.product_id), None)
    requested_quantity = payload.quantity + (existing.quantity if existing else 0)
    if requested_quantity > product.stock_quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")

    if existing:
        existing.quantity = requested_quantity
        existing.unit_price = product.price
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=payload.quantity,
                unit_price=product.price,
                currency=settings.default_currency,
            )
        )

    await db.commit()
    refreshed = await _load_cart(db, current_profile.id)
    return _to_cart_response(refreshed)


@router.patch("/items/{item_id}", response_model=CartResponse)
async def update_cart_item(
    item_id: uuid.UUID,
    payload: CartItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> CartResponse:
    cart = await _get_or_create_cart(db, current_profile.id)

    item = next((entry for entry in cart.items if entry.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    product = await db.get(Product, item.product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is not available")
    if payload.quantity > product.stock_quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")

    item.quantity = payload.quantity
    item.unit_price = product.price

    await db.commit()
    refreshed = await _load_cart(db, current_profile.id)
    return _to_cart_response(refreshed)


@router.delete("/items/{item_id}", response_model=CartResponse)
async def remove_cart_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> CartResponse:
    cart = await _get_or_create_cart(db, current_profile.id)
    item = next((entry for entry in cart.items if entry.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    await db.delete(item)
    await db.commit()

    refreshed = await _load_cart(db, current_profile.id)
    return _to_cart_response(refreshed)
