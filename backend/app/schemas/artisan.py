from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.product import ProductResponse


class ArtisanSummaryResponse(BaseModel):
    id: UUID
    full_name: str | None
    shop_name: str | None
    bio: str | None
    profile_image_url: str | None
    active_product_count: int = 0
    units_sold: int = 0
    created_at: datetime
    updated_at: datetime


class ArtisanDetailResponse(ArtisanSummaryResponse):
    products: list[ProductResponse]
