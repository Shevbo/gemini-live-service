from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import settings

bearer_scheme = HTTPBearer()


@dataclass
class User:
    id: str
    name: str


def _build_users() -> dict[str, User]:
    return {
        settings.boris_token: User(id="boris", name="Борис"),
        settings.maria_token: User(id="maria", name="Мария"),
        settings.daniela_token: User(id="daniela", name="Даниэла"),
    }


USERS: dict[str, User] = {}


def get_users() -> dict[str, User]:
    global USERS
    if not USERS:
        USERS = _build_users()
    return USERS


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    user = get_users().get(credentials.credentials)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


def get_user_from_token(token: str) -> User | None:
    return get_users().get(token)
