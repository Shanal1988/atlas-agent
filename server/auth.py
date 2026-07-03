import os
import jwt
from fastapi import HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)
SECRET = os.environ.get("NEXTAUTH_SECRET", "")


def _validate_token(raw: str) -> dict:
    if not SECRET:
        raise HTTPException(500, "NEXTAUTH_SECRET not configured")
    try:
        payload = jwt.decode(
            raw,
            SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "name": payload.get("name"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except Exception:
        raise HTTPException(401, "Invalid token")


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Security(bearer),
    token: str | None = Query(None),
) -> dict:
    """Validates JWT from Authorization header or ?token= query param (for SSE)."""
    raw = creds.credentials if creds else token
    if not raw:
        raise HTTPException(401, "Not authenticated")
    return _validate_token(raw)
