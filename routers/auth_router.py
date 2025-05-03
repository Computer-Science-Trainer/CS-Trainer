from services.achievement_service import check_and_award
from fastapi import APIRouter, HTTPException, BackgroundTasks, File, Form, UploadFile, Header
from pydantic import BaseModel, EmailStr
from enum import Enum
import random
import os
import uuid
from services.user_service import save_user, change_db_users, get_user_by_email, delete_user_by_id
from security import create_access_token, decode_access_token, verify_password
from jwt import ExpiredSignatureError, InvalidTokenError

MAX_AVATAR_SIZE = 1024 * 300  # 300 KB
MAX_USERNAME_LEN = 32
MAX_EMAIL_LEN = 320
MAX_TELEGRAM_LEN = 255
MAX_GITHUB_LEN = 255
MAX_WEBSITE_LEN = 255
MAX_BIO_LEN = 500


router = APIRouter()


# Token and code utilities
def generate_verification_code() -> str:
    return f"{random.randint(0, 999999):06d}"


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
    AVATAR_TOO_LARGE = 'avatar_too_large'
    PASSWORD_LENGTH_INVALID = 'password_length_invalid'
    VERIFICATION_SUCCESS = 'verification_success'
    USERNAME_LENGTH_INVALID = 'username_length_invalid'
    EMAIL_LENGTH_INVALID = 'email_length_invalid'
    TELEGRAM_LENGTH_INVALID = 'telegram_length_invalid'
    GITHUB_LENGTH_INVALID = 'github_length_invalid'
    WEBSITE_LENGTH_INVALID = 'website_length_invalid'
    BIO_LENGTH_INVALID = 'bio_length_invalid'


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
def login(data: LoginRequest, background_tasks: BackgroundTasks):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=404, detail={
                'code': ErrorCodes.USER_NOT_FOUND})
    if not verify_password(data.password, user['password']):
        raise HTTPException(
            status_code=401, detail={
                'code': ErrorCodes.INVALID_CREDENTIALS})
    if not user['verified']:
        code = generate_verification_code()
        if change_db_users(
                data.email, ('verification_code', code)) != 'success':
            raise HTTPException(
                status_code=500, detail={
                    'code': ErrorCodes.SAVING_FAILED})
        print(f'Verification code for {data.email}: {code}')
        raise HTTPException(
            status_code=403, detail={
                'code': ErrorCodes.ACCOUNT_NOT_VERIFIED})
    access_token = create_access_token(
        {'sub': data.email, 'user_id': user['id']})
    background_tasks.add_task(check_and_award, user['id'], 'login')
    print(access_token)
    return {'access_token': access_token, 'token_type': 'bearer'}


@router.post('/register')
def register(data: RegisterRequest):
    print(data)
    if len(data.username) > MAX_USERNAME_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.USERNAME_LENGTH_INVALID})
    if len(data.email) > MAX_EMAIL_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.EMAIL_LENGTH_INVALID})
    if get_user_by_email(data.email):
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.USER_EXISTS})
    if len(data.password) < 8 or len(data.password) > 32:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.PASSWORD_LENGTH_INVALID})
    code = generate_verification_code()
    if save_user(data.email, data.password, data.username, False, code):
        raise HTTPException(
            status_code=500, detail={
                'code': ErrorCodes.SAVING_FAILED})
    print(f'Registration code for {data.email}: {code}')
    return {'message': {'code': ErrorCodes.REGISTRATION_SUCCESS},
            'verification_code': code}


@router.post('/verify')
def verify(data: VerifyRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=404, detail={
                'code': ErrorCodes.USER_NOT_FOUND})
    if data.code != user['verification_code']:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.INVALID_VERIFICATION_CODE})
    if change_db_users(data.email, ('verified', 1)) != 'success':
        raise HTTPException(
            status_code=500, detail={
                'code': ErrorCodes.SAVING_FAILED})
    access_token = create_access_token(
        {'sub': data.email, 'user_id': user['id']})
    check_and_award(user['id'], event="login")
    return {'access_token': access_token, 'token_type': 'bearer',
            'message': {'code': ErrorCodes.VERIFICATION_SUCCESS}}


@router.post('/recover')
def recover(data: RecoverRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=404, detail={
                'code': ErrorCodes.USER_NOT_FOUND})
    code = generate_verification_code()
    if change_db_users(data.email, ('verification_code', code)) != 'success':
        raise HTTPException(
            status_code=500, detail={
                'code': ErrorCodes.SAVING_FAILED})
    print(f'Recovery code for {data.email}: {code}')
    return {'message': {'code': ErrorCodes.VERIFICATION_CODE_SENT}}


@router.post('/recover/verify')
def recover_verify(data: RecoverVerifyRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=404, detail={
                'code': ErrorCodes.USER_NOT_FOUND})
    if data.code != user['verification_code']:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.INVALID_VERIFICATION_CODE})
    return {'message': {'code': 'recovery_verified'}}


@router.post('/recover/change')
def recover_change_password(data: ChangePasswordRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=404, detail={
                'code': ErrorCodes.USER_NOT_FOUND})
    if data.code != user['verification_code']:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.INVALID_VERIFICATION_CODE})
    if len(data.password) < 8 or len(data.password) > 32:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.PASSWORD_LENGTH_INVALID})
    if change_db_users(data.email, ('password', data.password),
                       ('verified', 1)) != 'success':
        raise HTTPException(
            status_code=500, detail={
                'code': ErrorCodes.SAVING_FAILED})
    access_token = create_access_token(
        {'sub': data.email, 'user_id': user['id']})
    return {'access_token': access_token, 'token_type': 'bearer',
            'message': {'code': ErrorCodes.PASSWORD_CHANGE_SUCCESS}}


@router.post('/verify/resend')
def resend_code(data: ResendCodeRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=404, detail={
                'code': ErrorCodes.USER_NOT_FOUND})
    if data.code_type == CodeType.VERIFICATION and user['verified']:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.ALREADY_VERIFIED})
    code = generate_verification_code()
    if change_db_users(data.email, ('verification_code', code)) != 'success':
        raise HTTPException(
            status_code=500, detail={
                'code': ErrorCodes.SAVING_FAILED})
    print(f'Resend code for {data.email}: {code}')
    return {'message': {'code': ErrorCodes.VERIFICATION_CODE_SENT}}


class UpdatePasswordRequest(BaseModel):
    oldPassword: str
    newPassword: str


@router.post('/change-password')
async def change_password(data: UpdatePasswordRequest,
                          authorization: str = Header(None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    user = get_user_by_email(payload.get("sub"))
    if not user:
        raise HTTPException(
            status_code=404, detail={
                "code": ErrorCodes.USER_NOT_FOUND})
    if not verify_password(data.oldPassword, user['password']):
        raise HTTPException(
            status_code=400, detail={
                "code": ErrorCodes.INVALID_CREDENTIALS})
    if len(data.newPassword) < 8 or len(data.newPassword) > 32:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.PASSWORD_LENGTH_INVALID})
    change_db_users(user['email'], ('password', data.newPassword))
    return {}


@router.patch('/update-profile')
async def update_profile(
    username: str = Form(None),
    email: str = Form(None),
    telegram: str = Form(None),
    github: str = Form(None),
    website: str = Form(None),
    bio: str = Form(None),
    removeAvatar: str = Form(None),
    avatar: UploadFile = File(None),
    authorization: str = Header(None, alias="Authorization")
):
    print(username, email, telegram, github, website, bio)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    user_id = payload.get('user_id')
    current_email = payload.get('sub')
    user = get_user_by_email(current_email)
    if username is not None and len(username) > MAX_USERNAME_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.USERNAME_LENGTH_INVALID})
    if email is not None and len(email) > MAX_EMAIL_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.EMAIL_LENGTH_INVALID})
    if telegram is not None and len(telegram) > MAX_TELEGRAM_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.TELEGRAM_LENGTH_INVALID})
    if github is not None and len(github) > MAX_GITHUB_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.GITHUB_LENGTH_INVALID})
    if website is not None and len(website) > MAX_WEBSITE_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.WEBSITE_LENGTH_INVALID})
    if bio is not None and len(bio) > MAX_BIO_LEN:
        raise HTTPException(
            status_code=400, detail={
                'code': ErrorCodes.BIO_LENGTH_INVALID})
    if removeAvatar == "true":
        path = user.get("avatar", "")
        if path.startswith("/uploads/"):
            filename = path.split("/uploads/")[-1]
            file_path = os.path.join("uploads", filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        change_db_users(current_email, ('avatar', ''))

    if avatar:
        data = await avatar.read()
        if len(data) > MAX_AVATAR_SIZE:
            raise HTTPException(
                status_code=400, detail={
                    'code': ErrorCodes.AVATAR_TOO_LARGE})
        os.makedirs('uploads', exist_ok=True)
        ext = avatar.filename.split('.')[-1]
        filename = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join('uploads', filename)
        with open(file_path, "wb") as f:
            f.write(data)
        change_db_users(current_email, ('avatar', f"/uploads/{filename}"))
    new_email = current_email
    if email and email != current_email:
        change_db_users(current_email, ('email', email))
        new_email = email
    for col, val in [('username', username), ('telegram', telegram),
                     ('github', github), ('website', website), ('bio', bio)]:
        if val is not None:
            change_db_users(new_email, (col, val))
    new_token = create_access_token({"sub": new_email, "user_id": user_id})
    return {"token": new_token}


@router.delete('/delete-account')
async def delete_account(
        authorization: str = Header(None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    user_id = payload.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    deleted = delete_user_by_id(user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail={"code": "delete_failed"})
    return {"message": "account_deleted"}
