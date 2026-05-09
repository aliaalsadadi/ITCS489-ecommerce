from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.constants import AdminTargetType, AuctionAction, AuctionStatus, BidStatus, OrderStatus
from app.models.admin_action_log import AdminActionLog
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.profile import Profile

settings = get_settings()


@dataclass
class PlaceBidResult:
    auction: Auction
    bid: Bid
    outbid_bidder_id: UUID | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_status_for_time(auction: Auction) -> None:
    now = _now()
    if auction.status == AuctionStatus.SCHEDULED.value and auction.start_time <= now < auction.end_time:
        auction.status = AuctionStatus.ACTIVE.value
    if auction.status in {AuctionStatus.SCHEDULED.value, AuctionStatus.ACTIVE.value} and now >= auction.end_time:
        auction.status = AuctionStatus.CLOSED.value


def minimum_next_bid(auction: Auction) -> Decimal:
    return Decimal(auction.current_highest_bid) + Decimal(auction.min_increment)


async def get_auction_for_update(db: AsyncSession, auction_id: UUID) -> Auction | None:
    stmt: Select[tuple[Auction]] = select(Auction).where(Auction.id == auction_id).with_for_update()
    return (await db.scalars(stmt)).first()


async def place_bid(
    db: AsyncSession,
    auction_id: UUID,
    bidder: Profile,
    bid_amount: Decimal,
) -> PlaceBidResult:
    auction = await get_auction_for_update(db, auction_id)
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")

    _normalize_status_for_time(auction)

    if auction.status != AuctionStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Auction is not active")
    if bidder.id == auction.seller_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seller cannot bid on own auction")
    if bid_amount < minimum_next_bid(auction):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bid too low. Minimum next bid is {minimum_next_bid(auction)}",
        )

    previous_top_stmt = (
        select(Bid)
        .where(Bid.auction_id == auction.id, Bid.status == BidStatus.ACTIVE.value)
        .order_by(Bid.bid_amount.desc(), Bid.created_at.desc())
    )
    previous_top = (await db.scalars(previous_top_stmt)).first()
    outbid_bidder_id: UUID | None = None
    if previous_top and previous_top.bidder_id != bidder.id:
        previous_top.status = BidStatus.OUTBID.value
        outbid_bidder_id = previous_top.bidder_id

    previous_same_bidder_stmt = select(Bid).where(
        Bid.auction_id == auction.id,
        Bid.bidder_id == bidder.id,
        Bid.status == BidStatus.ACTIVE.value,
    )
    previous_same_bidder = list((await db.scalars(previous_same_bidder_stmt)).all())
    for old_bid in previous_same_bidder:
        old_bid.status = BidStatus.OUTBID.value

    new_bid = Bid(
        auction_id=auction.id,
        bidder_id=bidder.id,
        bid_amount=bid_amount,
        status=BidStatus.ACTIVE.value,
    )
    db.add(new_bid)

    auction.current_highest_bid = bid_amount
    auction.highest_bidder_id = bidder.id

    await db.commit()
    await db.refresh(auction)
    await db.refresh(new_bid)

    return PlaceBidResult(auction=auction, bid=new_bid, outbid_bidder_id=outbid_bidder_id)


async def close_auction(db: AsyncSession, auction_id: UUID, closed_by: Profile | None = None) -> Auction:
    auction = await get_auction_for_update(db, auction_id)
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")

    if closed_by is not None and closed_by.role != "admin" and auction.seller_id != closed_by.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    if auction.status in {AuctionStatus.CLOSED.value, AuctionStatus.CANCELED.value}:
        return auction

    winner_bid_stmt = (
        select(Bid)
        .where(Bid.auction_id == auction.id)
        .order_by(Bid.bid_amount.desc(), Bid.created_at.asc())
    )
    winner_bid = (await db.scalars(winner_bid_stmt)).first()

    auction.status = AuctionStatus.CLOSED.value
    order_id: UUID | None = None
    if winner_bid is not None:
        auction.highest_bidder_id = winner_bid.bidder_id
        auction.current_highest_bid = winner_bid.bid_amount
        winner_bid.status = BidStatus.WON.value

        product = await db.get(Product, auction.product_id)

        order = Order(
            customer_id=winner_bid.bidder_id,
            status=OrderStatus.PENDING.value,
            total_amount=winner_bid.bid_amount,
            currency=settings.default_currency,
            shipping_address="AUCTION_PENDING_SHIPPING_ADDRESS",
            payment_transaction_id=None,
        )
        db.add(order)
        await db.flush()
        order_id = order.id

        product_name = f"Auction Item {auction.product_id}"
        artist_id: UUID | None = auction.seller_id
        if product is not None:
            product_name = product.name
            artist_id = product.artist_id
            if product.stock_quantity > 0:
                product.stock_quantity -= 1

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=auction.product_id,
                artist_id=artist_id,
                product_name=product_name,
                quantity=1,
                unit_price=winner_bid.bid_amount,
            )
        )

    await db.commit()
    await db.refresh(auction)

    # Log auction closure
    admin_id = closed_by.id if closed_by is not None else None
    db.add(
        AdminActionLog(
            admin_id=admin_id,
            action=AuctionAction.CLOSED.value,
            target_type=AdminTargetType.AUCTION.value,
            target_id=str(auction.id),
            details={
                "auction_id": str(auction.id),
                "product_id": str(auction.product_id),
                "seller_id": str(auction.seller_id),
                "winner_id": str(auction.highest_bidder_id) if auction.highest_bidder_id else None,
                "winning_bid_amount": str(auction.current_highest_bid) if auction.highest_bidder_id else None,
                "order_id": str(order_id) if order_id else None,
                "closed_by": "system" if closed_by is None else str(closed_by.id),
            },
        )
    )
    await db.commit()

    return auction


async def auto_close_expired_auctions(db: AsyncSession) -> list[Auction]:
    now = _now()
    stmt = select(Auction).where(
        Auction.status.in_([AuctionStatus.ACTIVE.value, AuctionStatus.SCHEDULED.value]),
        Auction.end_time <= now,
    )
    candidates = list((await db.scalars(stmt)).all())

    closed: list[Auction] = []
    for auction in candidates:
        closed.append(await close_auction(db, auction.id, closed_by=None))

    return closed


async def list_recent_bids(db: AsyncSession, auction_id: UUID, limit: int = 20) -> list[Bid]:
    stmt = (
        select(Bid)
        .where(Bid.auction_id == auction_id)
        .options(selectinload(Bid.bidder))
        .order_by(Bid.created_at.desc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


async def get_auction_detail(db: AsyncSession, auction_id: UUID) -> Auction | None:
    stmt = (
        select(Auction)
        .where(Auction.id == auction_id)
        .options(
            selectinload(Auction.bids),
            selectinload(Auction.product),
            selectinload(Auction.seller),
            selectinload(Auction.highest_bidder),
        )
    )
    return (await db.scalars(stmt)).first()
