"""
Auth Dependencies
-----------------
FastAPI dependencies for extracting the current user from a JWT,
either required (protected routes) or optional (public + personalized routes).
"""
from typing import Optional

from fastapi import Header, HTTPException

from services.auth import decode_access_token
from services.document_repo import get_user_by_id


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """
    Returns the current user dict if a valid token is present, else None.
    Use this for routes that should work for both logged-in and anonymous users
    (e.g. /documents, /chat) where anonymous users see only public/demo content.
    """
    token = _extract_token(authorization)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = get_user_by_id(user_id)
    return user


async def get_current_user_required(authorization: Optional[str] = Header(None)) -> dict:
    """
    Returns the current user dict, or raises 401 if no valid token is present.
    Use this for routes that require login (e.g. /upload).
    """
    user = await get_current_user_optional(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user