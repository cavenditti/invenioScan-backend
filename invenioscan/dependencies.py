from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from invenioscan.adapters.base import InvenioAdapter
from invenioscan.adapters.invenio_ils import InvenioILSAdapter
from invenioscan.auth import decode_access_token
from invenioscan.schemas import CurrentUserResponse
from invenioscan.settings import Settings, get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_invenio_adapter(settings: Annotated[Settings, Depends(get_settings)]) -> InvenioAdapter:
    return InvenioILSAdapter(settings)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUserResponse:
    return decode_access_token(token, settings)