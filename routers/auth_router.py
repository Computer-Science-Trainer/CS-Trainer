from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from enum import Enum
import random
from services.user_service import save_user, change_db_users, get_user_by_email

router = APIRouter()

# Token and code utilities

def generate_verification_code() -> str:
    return f"{random.randint(0, 999999):06d}"

def generate_token(email: str) -> str:
    return f"fake-token-for-{email}"

# Error code constants
class ErrorCodes:
    ALREADY_VERIFIED = 'already_verified'
    SAVING_FAILED = 'saving_failed'
    USER_NOT_FOUND = 'user_not_found'
    INVALID_CREDENTIALS = 'invalid_credentials'
    USER_EXISTS = 'user_exists'
    INVALID_VERIFICATION_CODE = 'invalid_verification_code'
    ACCOUNT_NOT_VERIFIED = 'account_not_verified'
    PASSWORD_CHANGE_SUCCESS = 'password_change_success'
    VERIFICATION_CODE_SENT = 'verification_code_sent'
    REGISTRATION_SUCCESS = 'registration_success'
    VERIFICATION_SUCCESS = 'verification_success'

# Request models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: str

class VerifyRequest(BaseModel):
    email: EmailStr
    code: str

class RecoverRequest(BaseModel):
    email: EmailStr

class RecoverVerifyRequest(BaseModel):
    email: EmailStr
    code: str

class ChangePasswordRequest(BaseModel):
    email: EmailStr
    code: str
    password: str

class CodeType(str, Enum):
    VERIFICATION = 'verification'
    RECOVERY = 'recovery'

class ResendCodeRequest(BaseModel):
    email: EmailStr
    code_type: CodeType

# Endpoints
@router.post('/login')
def login(data: LoginRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=404, detail={'code': ErrorCodes.USER_NOT_FOUND})
    if data.password != user['password']:
        raise HTTPException(status_code=401, detail={'code': ErrorCodes.INVALID_CREDENTIALS})
    if not user['verified']:
        code = generate_verification_code()
        if change_db_users(data.email, ('verification_code', code)) != 'success':
            raise HTTPException(status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
        print(f'Verification code for {data.email}: {code}')
        raise HTTPException(status_code=403, detail={'code': ErrorCodes.ACCOUNT_NOT_VERIFIED})
    return {'token': generate_token(data.email)}

@router.post('/register')
def register(data: RegisterRequest):
    if get_user_by_email(data.email):
        raise HTTPException(status_code=400, detail={'code': ErrorCodes.USER_EXISTS})
    code = generate_verification_code()
    if save_user(data.email, data.password, data.username, False, code) != 'success':
        raise HTTPException(status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
    print(f'Registration code for {data.email}: {code}')
    return {'message': {'code': ErrorCodes.REGISTRATION_SUCCESS}, 'verification_code': code}

@router.post('/verify')
def verify(data: VerifyRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=404, detail={'code': ErrorCodes.USER_NOT_FOUND})
    if data.code != user['verification_code']:
        raise HTTPException(status_code=400, detail={'code': ErrorCodes.INVALID_VERIFICATION_CODE})
    if change_db_users(data.email, ('verified', 1)) != 'success':
        raise HTTPException(status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
    return {'token': generate_token(data.email), 'message': {'code': ErrorCodes.VERIFICATION_SUCCESS}}

@router.post('/recover')
def recover(data: RecoverRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=404, detail={'code': ErrorCodes.USER_NOT_FOUND})
    code = generate_verification_code()
    if change_db_users(data.email, ('verification_code', code)) != 'success':
        raise HTTPException(status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
    print(f'Recovery code for {data.email}: {code}')
    return {'message': {'code': ErrorCodes.VERIFICATION_CODE_SENT}}

@router.post('/recover/verify')
def recover_verify(data: RecoverVerifyRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=404, detail={'code': ErrorCodes.USER_NOT_FOUND})
    if data.code != user['verification_code']:
        raise HTTPException(status_code=400, detail={'code': ErrorCodes.INVALID_VERIFICATION_CODE})
    return {'message': {'code': 'recovery_verified'}}

@router.post('/recover/change')
def change_password(data: ChangePasswordRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=404, detail={'code': ErrorCodes.USER_NOT_FOUND})
    if data.code != user['verification_code']:
        raise HTTPException(status_code=400, detail={'code': ErrorCodes.INVALID_VERIFICATION_CODE})
    if change_db_users(data.email, ('password', data.password), ('verified', 1)) != 'success':
        raise HTTPException(status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
    return {'token': generate_token(data.email), 'message': {'code': ErrorCodes.PASSWORD_CHANGE_SUCCESS}}

@router.post('/verify/resend')
def resend_code(data: ResendCodeRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=404, detail={'code': ErrorCodes.USER_NOT_FOUND})
    if data.code_type == CodeType.VERIFICATION and user['verified']:
        raise HTTPException(status_code=400, detail={'code': ErrorCodes.ALREADY_VERIFIED})
    code = generate_verification_code()
    if change_db_users(data.email, ('verification_code', code)) != 'success':
        raise HTTPException(status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
    print(f'Resend code for {data.email}: {code}')
    return {'message': {'code': ErrorCodes.VERIFICATION_CODE_SENT}}
