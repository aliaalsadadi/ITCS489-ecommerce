from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import UserRole
from app.db.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.CUSTOMER.value)

    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shop_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    wallet_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products = relationship("Product", back_populates="artist")
    cart = relationship("Cart", back_populates="customer", uselist=False)
    orders = relationship("Order", back_populates="customer")
    sales = relationship("OrderItem", back_populates="artist")
    auctions_created = relationship("Auction", foreign_keys="Auction.seller_id", back_populates="seller")
    auctions_won = relationship("Auction", foreign_keys="Auction.highest_bidder_id", back_populates="highest_bidder")
    bids = relationship("Bid", back_populates="bidder")
    admin_actions = relationship("AdminActionLog", back_populates="admin")
