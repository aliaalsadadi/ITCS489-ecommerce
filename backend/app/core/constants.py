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


class ProductAction(StrEnum):
    CREATED = "product_created"
    UPDATED = "product_updated"
    DELETED = "product_deleted"


class AuctionAction(StrEnum):
    CREATED = "auction_created"
    CLOSED = "auction_closed"
    CANCELED = "auction_canceled"


class BidAction(StrEnum):
    PLACED = "bid_placed"
    OUTBID = "bid_outbid"


class OrderAction(StrEnum):
    CREATED = "order_created"


class PaymentAction(StrEnum):
    ATTEMPTED = "payment_attempted"
    SUCCEEDED = "payment_succeeded"
    FAILED = "payment_failed"
