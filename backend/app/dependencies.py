from fastapi import HTTPException, Security
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
        return {"id": user.id, "email": user.email, "token": token}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
