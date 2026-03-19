from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from invenioscan.schemas import CurrentUserResponse
from invenioscan.settings import Settings


def authenticate_operator(username: str, password: str, settings: Settings) -> CurrentUserResponse:
    if username != settings.bootstrap_username or password != settings.bootstrap_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return CurrentUserResponse(username=username)


def create_access_token(subject: str, settings: Settings) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_access_token_exp_minutes)
    expires_at = datetime.now(UTC) + expires_delta
    payload = {
        "sub": subject,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str, settings: Settings) -> CurrentUserResponse:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return CurrentUserResponse(username=subject)