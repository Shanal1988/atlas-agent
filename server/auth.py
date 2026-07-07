import os
import jwt
from fastapi import HTTPException, Request

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
            leeway=30,  # tolerate up to 30s clock skew
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


def get_current_user(request: Request) -> dict:
    """Validates JWT from Authorization header or ?token= query param (for SSE)."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return _validate_token(auth[7:])
    token = request.query_params.get("token")
    if token:
        return _validate_token(token)
    raise HTTPException(401, "Not authenticated")
