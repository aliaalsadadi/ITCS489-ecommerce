import uuid

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.db.session import get_db
from app.models.profile import Profile
from app.services.supabase_auth_service import validate_supabase_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_profile(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = await validate_supabase_access_token(credentials.credentials)
    user_id = uuid.UUID(payload["id"])
    email = payload.get("email") or ""
    metadata = payload.get("user_metadata") or {}

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

    changed = False
    if email and profile.email != email:
        profile.email = email
        changed = True
    if changed:
        await db.commit()
        await db.refresh(profile)

    if profile.is_suspended and profile.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended")

    return profile


def require_roles(*roles: UserRole):
    allowed = {role.value for role in roles}

    async def _guard(current_profile: Profile = Depends(get_current_profile)) -> Profile:
        if current_profile.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return current_profile

    return _guard
