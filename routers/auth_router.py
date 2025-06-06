from services.achievement_service import check_and_award
from services.user_service import save_user, change_db_users, get_user_by_email, \
    delete_user_by_id, get_user_by_telegram, set_refresh_token
from fastapi import APIRouter, HTTPException, BackgroundTasks, File, Form, UploadFile, Header, status
from pydantic import BaseModel, EmailStr
from enum import Enum
import random
import os
import uuid
import secrets
import re
from security import create_access_token, decode_access_token, verify_password
from jwt import ExpiredSignatureError, InvalidTokenError
from services.email_service import send_verification_email
from typing import Optional

MAX_AVATAR_SIZE = 1024 * 300  # 300 KB
MAX_USERNAME_LEN = 32
MAX_EMAIL_LEN = 320
MAX_TELEGRAM_LEN = 255
MAX_GITHUB_LEN = 255
MAX_WEBSITE_LEN = 255
MAX_BIO_LEN = 500

# Blacklisted usernames (case-insensitive)
USERNAME_BLACKLIST = {'admin', 'tests', 'about', 'settings', 'leaderboard'}

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
    USERNAME_FORMAT_INVALID = 'username_format_invalid'
    USERNAME_BLACKLISTED = 'username_blacklisted'


# Request models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: str
    telegram_username: Optional[str] = None


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


# New request models for Telegram functionality
class CheckTelegramRequest(BaseModel):
    telegram_username: str


class LoginTelegramRequest(BaseModel):
    telegram_username: str


class LinkTelegramRequest(BaseModel):
    telegram_username: str
    email: EmailStr
    password: str


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
    refresh_token = secrets.token_urlsafe(32)
    set_refresh_token(user['id'], refresh_token)
    background_tasks.add_task(check_and_award, user['id'], 'login')
    return {'access_token': access_token,
            'token_type': 'bearer', 'refresh_token': refresh_token}


@router.post('/register', status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, background_tasks: BackgroundTasks):
    # Validate username length
    if not (3 < len(data.username) <= MAX_USERNAME_LEN):
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.USERNAME_LENGTH_INVALID})
    if not re.fullmatch(r'^[A-Za-z0-9_-]+$', data.username):
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.USERNAME_FORMAT_INVALID})
    # Reject blacklisted usernames
    if data.username.lower() in USERNAME_BLACKLIST:
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.USERNAME_BLACKLISTED})
    # Validate email length
    if len(data.email) > MAX_EMAIL_LEN:
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.EMAIL_LENGTH_INVALID})
    # Check if user exists
    if get_user_by_email(data.email):
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.USER_EXISTS})
    # Validate password length
    if len(data.password) < 8 or len(data.password) > 32:
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.PASSWORD_LENGTH_INVALID})
    # Generate verification code and save user
    code = generate_verification_code()
    if save_user(data.email, data.password, data.username, False, code):
        raise HTTPException(
            status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
    # Link Telegram username if provided
    if data.telegram_username is not None:
        if len(data.telegram_username) > MAX_TELEGRAM_LEN:
            raise HTTPException(
                status_code=400, detail={'code': ErrorCodes.TELEGRAM_LENGTH_INVALID})
        if change_db_users(data.email, ('telegram',
                           data.telegram_username)) != 'success':
            raise HTTPException(
                status_code=500, detail={'code': ErrorCodes.SAVING_FAILED})
    # Send verification email
    background_tasks.add_task(send_verification_email, data.email, code)
    return {'pending_verification': True}


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
def resend_code(data: ResendCodeRequest, background_tasks: BackgroundTasks):
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
    # send verification email asynchronously
    background_tasks.add_task(send_verification_email, data.email, code)
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
    # Validate username format: only English letters, digits, underscores and
    # hyphens
    if username is not None and not re.fullmatch(
            r'^[A-Za-z0-9_-]+$', username):
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.USERNAME_FORMAT_INVALID})
    # Reject blacklisted usernames
    if username is not None and username.lower() in USERNAME_BLACKLIST:
        raise HTTPException(
            status_code=400, detail={'code': ErrorCodes.USERNAME_BLACKLISTED})
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


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post('/refresh')
def refresh_token_endpoint(data: RefreshRequest):
    from services.user_service import get_user_by_refresh_token
    user = get_user_by_refresh_token(data.refresh_token)
    if not user:
        raise HTTPException(
            status_code=401, detail={
                "code": "invalid_refresh_token"})
    access_token = create_access_token(
        {'sub': user['email'], 'user_id': user['id']})
    return {'access_token': access_token, 'token_type': 'bearer'}


@router.post('/check-telegram')
def check_telegram(data: CheckTelegramRequest):
    exists = get_user_by_telegram(data.telegram_username) is not None
    return {'exists': exists}


@router.post('/login-telegram')
def login_telegram(data: LoginTelegramRequest,
                   background_tasks: BackgroundTasks):
    user = get_user_by_telegram(data.telegram_username)
    if not user:
        raise HTTPException(
            status_code=401, detail={
                'code': ErrorCodes.INVALID_CREDENTIALS})
    if not user['verified']:
        raise HTTPException(
            status_code=401, detail={
                'code': ErrorCodes.ACCOUNT_NOT_VERIFIED})
    access_token = create_access_token(
        {'sub': user['email'], 'user_id': user['id']})
    refresh_token = secrets.token_urlsafe(32)
    set_refresh_token(user['id'], refresh_token)
    background_tasks.add_task(check_and_award, user['id'], 'login')
    return {'username': user['username'],
            'access_token': access_token, 'refresh_token': refresh_token}


@router.post('/link-telegram')
def link_telegram(data: LinkTelegramRequest):
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=404, detail={
                'code': ErrorCodes.USER_NOT_FOUND})
    if not verify_password(data.password, user['password']):
        raise HTTPException(
            status_code=401, detail={
                'code': ErrorCodes.INVALID_CREDENTIALS})
    if change_db_users(data.email, ('telegram',
                       data.telegram_username)) != 'success':
        raise HTTPException(
            status_code=500, detail={
                'code': ErrorCodes.SAVING_FAILED})
    return {'linked': True}
