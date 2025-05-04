from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from services.user_service import get_user_by_email
from security import decode_access_token
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from security import get_current_user
from services.user_service import get_user_by_email
from models.schemas import UserOut

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def me(current_user: UserOut = Depends(get_current_user)):
    user = get_user_by_email(current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        id=user["id"],
        email=user["email"],
        username=user["username"]
    )