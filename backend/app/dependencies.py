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
        return {"id": user.id, "email": user.email, "token": token, "role": role}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e


async def require_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
