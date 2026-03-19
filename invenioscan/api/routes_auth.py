from typing import Annotated

from fastapi import APIRouter, Depends

from invenioscan.auth import authenticate_operator, create_access_token
from invenioscan.dependencies import get_current_user
from invenioscan.schemas import CurrentUserResponse, LoginRequest, TokenResponse
from invenioscan.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, settings: Annotated[Settings, Depends(get_settings)]) -> TokenResponse:
    user = authenticate_operator(payload.username, payload.password, settings)
    token, expires_in = create_access_token(user.username, settings)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(user: Annotated[CurrentUserResponse, Depends(get_current_user)]) -> CurrentUserResponse:
    return user