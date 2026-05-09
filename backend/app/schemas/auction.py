from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AuctionCreateRequest(BaseModel):
    product_id: UUID
    starting_price: Decimal = Field(gt=0)
    min_increment: Decimal = Field(default=Decimal("1.00"), gt=0)
    start_time: datetime | None = None
    end_time: datetime


class AuctionStatusResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    product_image_url: str | None = None
    seller_id: UUID
    seller_name: str | None = None
    highest_bidder_id: UUID | None
    highest_bidder_name: str | None = None
    status: str
    starting_price: Decimal
    min_increment: Decimal
    current_highest_bid: Decimal
    start_time: datetime
    end_time: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuctionListResponse(BaseModel):
    items: list[AuctionStatusResponse]
    total: int
    limit: int
    offset: int
