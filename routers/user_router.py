from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from services.user_service import get_user_by_email
from security import decode_access_token
from jwt import ExpiredSignatureError, InvalidTokenError

router = APIRouter()


# Output model for /api/me
class UserOut(BaseModel):
    id: int
    email: str
    username: str


@router.get("/me", response_model=UserOut)
def me(authorization: str = Header(None, alias="Authorization")):
    if authorization and authorization.startswith("Bearer "):
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
