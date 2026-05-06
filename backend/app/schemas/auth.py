from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import UserRole


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    shop_name: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=1000)
    profile_image_url: str | None = Field(default=None, max_length=1000)


class RoleUpdateRequest(BaseModel):
    role: UserRole


class ProfileResponse(BaseModel):
    id: UUID
    email: str
    role: str
    full_name: str | None
    shop_name: str | None
    bio: str | None
    profile_image_url: str | None
    wallet_balance: Decimal
    is_suspended: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
