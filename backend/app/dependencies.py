from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.database import get_supabase_client

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    token = credentials.credentials
    try:
        client = get_supabase_client()
        response = client.auth.get_user(token)
        user = response.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        role = (user.app_metadata or {}).get("role", "user")

        # Check if user is deactivated via user_profiles
        profile = client.table("user_profiles").select("is_active").eq("user_id", str(user.id)).execute()
        if profile.data:
            if not profile.data[0]["is_active"]:
                raise HTTPException(status_code=403, detail="Account deactivated")
        else:
            # Auto-create profile for new signups
            client.table("user_profiles").insert({
                "user_id": str(user.id),
                "display_name": user.email,
                "is_active": True,
            }).execute()

        return {"id": user.id, "email": user.email, "token": token, "role": role}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e


async def require_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
