from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from services.user_service import get_user_by_email, get_user_by_username, get_user_tests
from security import decode_access_token
from jwt import ExpiredSignatureError, InvalidTokenError
from typing import List, Optional
import datetime
from services.achievement_service import get_user_achievements

router = APIRouter()


class UserOut(BaseModel):
    id: int
    email: str
    username: str


class AchievementOut(BaseModel):
    code: str
    emoji: str
    unlocked: bool
    unlocked_at: Optional[datetime.datetime] = None


class TestOut(BaseModel):
    id: int
    type: str
    section: str
    passed: int
    total: int
    average: float
    topics: List[str]
    created_at: datetime.datetime


@router.get("/me", response_model=UserOut)
def me(authorization: str = Header(None, alias="Authorization")):
    if (authorization and authorization.startswith("Bearer ")):
        token = authorization.split(" ", 1)[1]
    else:
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})

    return UserOut(id=user["id"], email=user["email"],
                   username=user["username"])


@router.get("/users/{user_id}/achievements",
            response_model=List[AchievementOut])
def user_achievements_by_id(user_id: int):
    unlocked = get_user_achievements(user_id)
    return [
        {
            'code': a['code'],
            'emoji': a.get('emoji'),
            'unlocked': True,
            'unlocked_at': a['unlocked_at']
        }
        for a in unlocked
    ]


@router.get("/user/{username}/achievements",
            response_model=List[AchievementOut])
def user_achievements_by_username(username: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    return user_achievements_by_id(user['id'])


@router.get("/user/{username}/tests", response_model=List[TestOut])
def user_tests_by_username(username: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    return get_user_tests(user['id'])
