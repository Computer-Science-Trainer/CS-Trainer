from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from services.user_service import get_user_by_email

router = APIRouter()

# Output model for /api/me
class UserOut(BaseModel):
    id: int
    email: str
    username: str

@router.get("/me", response_model=UserOut)
def me(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    token = authorization.split(" ", 1)[1]
    prefix = "fake-token-for-"
    if not token.startswith(prefix):
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    email = token[len(prefix):]
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    return UserOut(
        id=user['id'],
        email=user['email'],
        username=user['username']
    )
