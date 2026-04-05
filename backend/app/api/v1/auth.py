from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_profile
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.auth import ProfileResponse, ProfileUpdateRequest, RoleUpdateRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=ProfileResponse)
async def get_me(current_profile: Profile = Depends(get_current_profile)) -> Profile:
    return current_profile


@router.put("/me", response_model=ProfileResponse)
async def update_me(
    payload: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Profile:
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(current_profile, field_name, value)

    await db.commit()
    await db.refresh(current_profile)
    return current_profile


@router.post("/me/role", response_model=ProfileResponse)
async def update_my_role(
    payload: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Profile:
    current_profile.role = payload.role.value
    await db.commit()
    await db.refresh(current_profile)
    return current_profile
