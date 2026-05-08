from fastapi import HTTPException, status
import httpx

from app.core.config import get_settings


def _supabase_headers(api_key: str, bearer_token: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer_token or api_key}",
        "apikey": api_key,
    }


async def supabase_user_email_exists(email: str) -> bool:
    settings = get_settings()
    if not settings.supabase_service_role_key:
        return False

    target_email = email.strip().lower()
    headers = _supabase_headers(settings.supabase_service_role_key)

    async with httpx.AsyncClient(timeout=10.0) as client:
        for page in range(1, 11):
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/admin/users",
                headers=headers,
                params={"page": page, "per_page": 100},
            )
            if response.status_code != status.HTTP_200_OK:
                return False

            payload = response.json()
            users = payload.get("users", []) if isinstance(payload, dict) else []
            if any(str(user.get("email", "")).strip().lower() == target_email for user in users):
                return True
            if len(users) < 100:
                return False

    return False


async def validate_supabase_access_token(access_token: str) -> dict:
    settings = get_settings()

    headers = _supabase_headers(settings.supabase_anon_key, access_token)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{settings.supabase_url}/auth/v1/user", headers=headers)

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    payload = response.json()
    if not payload.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed auth payload")

    return payload
