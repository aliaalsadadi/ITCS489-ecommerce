from fastapi import HTTPException, status
import httpx

from app.core.config import get_settings


async def validate_supabase_access_token(access_token: str) -> dict:
    settings = get_settings()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": settings.supabase_anon_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{settings.supabase_url}/auth/v1/user", headers=headers)

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    payload = response.json()
    if not payload.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed auth payload")

    return payload
