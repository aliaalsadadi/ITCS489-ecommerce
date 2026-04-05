from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_profile, require_roles
from app.core.constants import AuctionStatus, UserRole
from app.db.session import AsyncSessionLocal, get_db
from app.models.auction import Auction
from app.models.product import Product
from app.models.profile import Profile
from app.schemas.auction import AuctionCreateRequest, AuctionListResponse, AuctionStatusResponse
from app.schemas.bid import AuctionClosedEvent, AuctionDetailResponse, BidCreateRequest, BidOutbidEvent, BidPlacedEvent
from app.services.auction_service import (
    close_auction,
    get_auction_detail,
    list_recent_bids,
    minimum_next_bid,
    place_bid,
)
from app.services.supabase_auth_service import validate_supabase_access_token
from app.services.ws_manager import auction_ws_manager

router = APIRouter(prefix="/auctions", tags=["auctions"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _resolve_ws_profile(token: str) -> Profile:
    payload = await validate_supabase_access_token(token)
    user_id = uuid.UUID(payload["id"])
    email = payload.get("email") or ""
    metadata = payload.get("user_metadata") or {}

    async with AsyncSessionLocal() as db:
        profile = await db.get(Profile, user_id)
        if profile is None:
            profile = Profile(
                id=user_id,
                email=email,
                full_name=metadata.get("full_name"),
                role=UserRole.CUSTOMER.value,
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
            return profile

        if email and profile.email != email:
            profile.email = email
            await db.commit()
            await db.refresh(profile)

        return profile


@router.post("", response_model=AuctionStatusResponse)
async def create_auction(
    payload: AuctionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> Auction:
    if payload.end_time <= _utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_time must be in the future")

    product = await db.get(Product, payload.product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if current_profile.role != UserRole.ADMIN.value and product.artist_id != current_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    start_time = payload.start_time or _utc_now()
    if payload.end_time <= start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_time must be after start_time")

    auction = Auction(
        product_id=product.id,
        seller_id=product.artist_id,
        status=(AuctionStatus.ACTIVE.value if start_time <= _utc_now() else AuctionStatus.SCHEDULED.value),
        starting_price=payload.starting_price,
        min_increment=payload.min_increment,
        current_highest_bid=payload.starting_price,
        start_time=start_time,
        end_time=payload.end_time,
    )
    db.add(auction)
    await db.commit()
    await db.refresh(auction)
    return auction


@router.get("", response_model=AuctionListResponse)
async def list_auctions(
    view: str = Query(default="active", pattern="^(active|upcoming|ended|all)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AuctionListResponse:
    now = _utc_now()

    stmt: Select[tuple[Auction]] = select(Auction)
    count_stmt = select(func.count()).select_from(Auction)

    if view == "active":
        condition = or_(
            Auction.status == AuctionStatus.ACTIVE.value,
            (Auction.status == AuctionStatus.SCHEDULED.value) & (Auction.start_time <= now) & (Auction.end_time > now),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    elif view == "upcoming":
        condition = (Auction.status == AuctionStatus.SCHEDULED.value) & (Auction.start_time > now)
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    elif view == "ended":
        condition = or_(
            Auction.status.in_([AuctionStatus.CLOSED.value, AuctionStatus.CANCELED.value]),
            Auction.end_time <= now,
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    stmt = stmt.order_by(Auction.created_at.desc()).offset(offset).limit(limit)
    items = list((await db.scalars(stmt)).all())
    total = (await db.execute(count_stmt)).scalar_one()

    return AuctionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{auction_id}", response_model=AuctionDetailResponse)
async def get_auction(
    auction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AuctionDetailResponse:
    auction = await get_auction_detail(db, auction_id)
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")

    bids = await list_recent_bids(db, auction.id, limit=20)

    return AuctionDetailResponse(
        auction_id=auction.id,
        status=auction.status,
        product_id=auction.product_id,
        seller_id=auction.seller_id,
        highest_bidder_id=auction.highest_bidder_id,
        current_highest_bid=auction.current_highest_bid,
        min_increment=auction.min_increment,
        start_time=auction.start_time,
        end_time=auction.end_time,
        recent_bids=bids,
        minimum_next_bid=minimum_next_bid(auction),
    )


@router.post("/{auction_id}/bids")
async def place_auction_bid(
    auction_id: uuid.UUID,
    payload: BidCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> dict:
    result = await place_bid(db, auction_id, current_profile, Decimal(payload.bid_amount))

    await auction_ws_manager.broadcast(
        result.auction.id,
        BidPlacedEvent(
            auction_id=result.auction.id,
            bidder_id=current_profile.id,
            bid_amount=result.bid.bid_amount,
            timestamp=result.bid.created_at,
        ).model_dump(mode="json"),
    )

    if result.outbid_bidder_id is not None:
        await auction_ws_manager.broadcast(
            result.auction.id,
            BidOutbidEvent(
                auction_id=result.auction.id,
                bidder_id=result.outbid_bidder_id,
                new_highest_bid=result.auction.current_highest_bid,
                timestamp=_utc_now(),
            ).model_dump(mode="json"),
        )

    return {
        "auction_id": result.auction.id,
        "current_highest_bid": result.auction.current_highest_bid,
        "highest_bidder_id": result.auction.highest_bidder_id,
        "bid": {
            "id": result.bid.id,
            "amount": result.bid.bid_amount,
            "status": result.bid.status,
            "created_at": result.bid.created_at,
        },
    }


@router.post("/{auction_id}/close", response_model=AuctionStatusResponse)
async def close_auction_endpoint(
    auction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> Auction:
    auction = await close_auction(db, auction_id, closed_by=current_profile)

    await auction_ws_manager.broadcast(
        auction.id,
        AuctionClosedEvent(
            auction_id=auction.id,
            winner_id=auction.highest_bidder_id,
            final_bid=auction.current_highest_bid if auction.highest_bidder_id else None,
            timestamp=_utc_now(),
        ).model_dump(mode="json"),
    )

    return auction


@router.websocket("/ws/live/{auction_id}")
async def auction_live_socket(websocket: WebSocket, auction_id: uuid.UUID) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    try:
        await _resolve_ws_profile(token)
    except Exception:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await auction_ws_manager.connect(auction_id, websocket)
    try:
        await auction_ws_manager.broadcast(
            auction_id,
            {
                "event": "ws_connected",
                "auction_id": str(auction_id),
                "timestamp": _utc_now().isoformat(),
            },
        )

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await auction_ws_manager.disconnect(auction_id, websocket)
    except Exception:
        await auction_ws_manager.disconnect(auction_id, websocket)
        await websocket.close(code=1011)
