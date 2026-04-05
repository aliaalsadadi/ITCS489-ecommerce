from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ARTISAN = "artisan"
    ADMIN = "admin"


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELED = "canceled"


class AuctionStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELED = "canceled"


class BidStatus(StrEnum):
    ACTIVE = "active"
    OUTBID = "outbid"
    WON = "won"
    CANCELED = "canceled"


class AdminTargetType(StrEnum):
    USER = "user"
    PRODUCT = "product"
    ORDER = "order"
    AUCTION = "auction"
