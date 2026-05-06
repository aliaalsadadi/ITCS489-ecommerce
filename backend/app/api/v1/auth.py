from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_profile
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.auth import ProfileResponse, ProfileUpdateRequest, RoleUpdateRequest

router = APIRouter(prefix="/auth", tags=["auth"])
PROFILE_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "profiles"
PROFILE_UPLOAD_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
}


def _guess_profile_image_suffix(upload: UploadFile) -> str:
    if upload.content_type and upload.content_type in PROFILE_UPLOAD_MIME_TYPES:
        return PROFILE_UPLOAD_MIME_TYPES[upload.content_type]
    if upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix:
            return suffix
    return ".bin"


async def _store_profile_image(request: Request, upload: UploadFile) -> str:
    if upload.content_type is None or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image")

    PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    image_bytes = await upload.read()
    filename = f"{uuid4().hex}{_guess_profile_image_suffix(upload)}"
    file_path = PROFILE_UPLOAD_DIR / filename
    file_path.write_bytes(image_bytes)
    return str(request.url_for("profile_images", path=filename))


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


@router.post("/me/profile-image", response_model=ProfileResponse)
async def upload_profile_image(
    request: Request,
    image_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Profile:
    current_profile.profile_image_url = await _store_profile_image(request, image_file)
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
