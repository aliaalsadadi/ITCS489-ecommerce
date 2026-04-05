from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AuctionStatus
from app.db.base import Base


class Auction(Base):
    __tablename__ = "auctions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"))
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"))
    highest_bidder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(32), default=AuctionStatus.SCHEDULED.value, index=True)

    starting_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    min_increment: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1.00"))
    current_highest_bid: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    start_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    end_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product = relationship("Product", back_populates="auctions")
    seller = relationship("Profile", foreign_keys=[seller_id], back_populates="auctions_created")
    highest_bidder = relationship("Profile", foreign_keys=[highest_bidder_id], back_populates="auctions_won")
    bids = relationship("Bid", back_populates="auction", cascade="all, delete-orphan", lazy="selectin")
