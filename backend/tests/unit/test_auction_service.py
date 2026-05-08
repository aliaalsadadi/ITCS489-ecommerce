from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.constants import AuctionStatus, UserRole
from app.models.auction import Auction
from app.models.profile import Profile
from app.services.auction_service import _normalize_status_for_time, minimum_next_bid, place_bid


class _FakeScalarResult:
    def __init__(self, rows: list[object]):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _FakeBidSession:
    def __init__(self, auction: Auction | None):
        self._auction = auction

    async def scalars(self, stmt):
        return _FakeScalarResult([] if self._auction is None else [self._auction])


def _auction(
    *,
    status: str = AuctionStatus.ACTIVE.value,
    seller_id=None,
    current_highest_bid: Decimal = Decimal("50.00"),
    min_increment: Decimal = Decimal("5.00"),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> Auction:
    now = datetime.now(timezone.utc)
    return Auction(
        id=uuid4(),
        product_id=uuid4(),
        seller_id=seller_id or uuid4(),
        status=status,
        starting_price=Decimal("50.00"),
        current_highest_bid=current_highest_bid,
        min_increment=min_increment,
        start_time=start_time or now - timedelta(minutes=5),
        end_time=end_time or now + timedelta(minutes=5),
    )


def _bidder(profile_id=None) -> Profile:
    return Profile(id=profile_id or uuid4(), email="bidder@example.com", role=UserRole.CUSTOMER.value)


@pytest.mark.unit
def test_minimum_next_bid() -> None:
    auction = _auction(current_highest_bid=Decimal("50.00"), min_increment=Decimal("5.00"))

    assert minimum_next_bid(auction) == Decimal("55.00")


@pytest.mark.unit
def test_normalize_status_starts_scheduled_auction() -> None:
    now = datetime.now(timezone.utc)
    auction = _auction(
        status=AuctionStatus.SCHEDULED.value,
        start_time=now - timedelta(minutes=1),
        end_time=now + timedelta(minutes=1),
    )

    _normalize_status_for_time(auction)

    assert auction.status == AuctionStatus.ACTIVE.value


@pytest.mark.unit
def test_normalize_status_closes_expired_scheduled_auction() -> None:
    now = datetime.now(timezone.utc)
    auction = _auction(
        status=AuctionStatus.SCHEDULED.value,
        start_time=now - timedelta(minutes=10),
        end_time=now - timedelta(minutes=1),
    )

    _normalize_status_for_time(auction)

    assert auction.status == AuctionStatus.CLOSED.value


@pytest.mark.unit
def test_normalize_status_closes_expired_active_auction() -> None:
    auction = _auction(status=AuctionStatus.ACTIVE.value, end_time=datetime.now(timezone.utc) - timedelta(minutes=1))

    _normalize_status_for_time(auction)

    assert auction.status == AuctionStatus.CLOSED.value


@pytest.mark.unit
def test_normalize_status_keeps_future_scheduled_auction() -> None:
    now = datetime.now(timezone.utc)
    auction = _auction(
        status=AuctionStatus.SCHEDULED.value,
        start_time=now + timedelta(minutes=1),
        end_time=now + timedelta(minutes=10),
    )

    _normalize_status_for_time(auction)

    assert auction.status == AuctionStatus.SCHEDULED.value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_place_bid_missing_auction_raises_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await place_bid(_FakeBidSession(None), uuid4(), _bidder(), Decimal("55.00"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Auction not found"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_place_bid_closed_auction_raises_400() -> None:
    auction = _auction(status=AuctionStatus.CLOSED.value)

    with pytest.raises(HTTPException) as exc_info:
        await place_bid(_FakeBidSession(auction), auction.id, _bidder(), Decimal("55.00"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Auction is not active"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_place_bid_rejects_seller_on_own_auction() -> None:
    seller_id = uuid4()
    auction = _auction(seller_id=seller_id)

    with pytest.raises(HTTPException) as exc_info:
        await place_bid(_FakeBidSession(auction), auction.id, _bidder(seller_id), Decimal("55.00"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Seller cannot bid on own auction"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_place_bid_rejects_bid_below_minimum() -> None:
    auction = _auction(current_highest_bid=Decimal("50.00"), min_increment=Decimal("5.00"))

    with pytest.raises(HTTPException) as exc_info:
        await place_bid(_FakeBidSession(auction), auction.id, _bidder(), Decimal("54.99"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Bid too low. Minimum next bid is 55.00"
