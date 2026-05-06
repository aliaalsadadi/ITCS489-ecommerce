from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import AuctionStatus, OrderStatus, UserRole


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    is_suspended: bool
    full_name: str | None
    shop_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserRoleUpdateRequest(BaseModel):
    role: UserRole


class AdminUserSuspensionRequest(BaseModel):
    is_suspended: bool


class AdminProductModerationRequest(BaseModel):
    is_active: bool


class AdminOrderStatusRequest(BaseModel):
    status: OrderStatus


class AdminAuctionStatusRequest(BaseModel):
    status: AuctionStatus = Field(description="Allowed: closed or canceled")


class AdminActionLogResponse(BaseModel):
    id: UUID
    admin_id: UUID | None
    action: str
    target_type: str
    target_id: str
    details: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class UnpaidAuctionSummary(BaseModel):
    count: int
    oldest_created_at: datetime | None
    total_amount: str
    currency: str


class UnpaidAuctionOrder(BaseModel):
    order_id: UUID
    customer_id: UUID
    customer_name: str | None
    customer_email: str
    auction_id: UUID
    product_id: UUID
    product_name: str
    winning_bid_amount: str
    created_at: datetime
    hours_pending: float
    status: str


class UnpaidAuctionOrdersResponse(BaseModel):
    items: list[UnpaidAuctionOrder]
    total: int


class AdminDashboardSummary(BaseModel):
    users_total: int
    users_suspended: int
    products_total: int
    orders_total: int
    auctions_total: int
    unpaid_auctions_count: int
    revenue_total: str
