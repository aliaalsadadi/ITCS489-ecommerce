from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import OrderStatus


class CheckoutRequest(BaseModel):
    card_token: str = Field(min_length=3, max_length=120)
    shipping_address: str = Field(min_length=5, max_length=2000)


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus
    tracking_number: str | None = Field(default=None, max_length=255)
    shipping_carrier: str | None = Field(default=None, max_length=120)
    shipping_method: str | None = Field(default=None, max_length=120)
    estimated_delivery_at: datetime | None = None


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID | None
    artist_id: UUID | None
    product_name: str
    quantity: int
    unit_price: Decimal


class OrderResponse(BaseModel):
    id: UUID
    customer_id: UUID
    status: str
    total_amount: Decimal
    currency: str
    shipping_address: str
    payment_transaction_id: str | None
    tracking_number: str | None
    shipping_carrier: str | None
    shipping_method: str | None
    estimated_delivery_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]

    model_config = {"from_attributes": True}
