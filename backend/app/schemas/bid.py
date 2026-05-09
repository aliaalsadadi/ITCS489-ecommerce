from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BidCreateRequest(BaseModel):
    bid_amount: Decimal = Field(gt=0)


class BidResponse(BaseModel):
    id: UUID
    auction_id: UUID
    bidder_id: UUID
    bidder_name: str | None = None
    bid_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuctionDetailResponse(BaseModel):
    auction_id: UUID
    status: str
    product_id: UUID
    product_name: str | None = None
    product_image_url: str | None = None
    seller_id: UUID
    seller_name: str | None = None
    highest_bidder_id: UUID | None
    highest_bidder_name: str | None = None
    current_highest_bid: Decimal
    min_increment: Decimal
    start_time: datetime
    end_time: datetime
    recent_bids: list[BidResponse]
    minimum_next_bid: Decimal


class BidPlacedEvent(BaseModel):
    event: str = "bid_placed"
    auction_id: UUID
    bidder_id: UUID
    bid_amount: Decimal
    timestamp: datetime


class BidOutbidEvent(BaseModel):
    event: str = "bid_outbid"
    auction_id: UUID
    bidder_id: UUID
    new_highest_bid: Decimal
    timestamp: datetime


class AuctionClosedEvent(BaseModel):
    event: str = "auction_closed"
    auction_id: UUID
    winner_id: UUID | None
    final_bid: Decimal | None
    timestamp: datetime
