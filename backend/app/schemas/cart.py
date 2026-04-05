from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CartItemCreateRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=100)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(ge=1, le=100)


class CartItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class CartResponse(BaseModel):
    id: UUID
    customer_id: UUID
    currency: str
    items: list[CartItemResponse]
    subtotal: Decimal
