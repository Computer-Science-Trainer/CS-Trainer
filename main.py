# Импортируем необходимые модули и библиотеки
from fastapi import FastAPI, HTTPException, Request  # FastAPI для создания API, HTTPException для обработки ошибок
from pydantic import BaseModel, EmailStr  # BaseModel для валидации данных, EmailStr для проверки email
import pymysql  # Для связи с базой данных
from typing import Dict  # Типизация словаря
from fastapi.middleware.cors import CORSMiddleware  # Middleware для настройки CORS
from enum import Enum  # Enum для создания перечислений
import random  # Для генерации случайных чисел
import uvicorn  # Для запуска приложения
from db_connection import (
    get_dict_users, save_user, change_db_users, get_leaderboard, verify_password,
    hash_password, validate_password
)
from jose import jwt, JWTError
from datetime import datetime, timedelta

# Создаем экземпляр приложения FastAPI
app = FastAPI()

# Добавление CORS middleware для управления доступом к API
# origins - список разрешенных источников (доменов), которые могут обращаться к API
# "*" - разрешает доступ с любого источника (используется только для разработки)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Разрешенные источники
    allow_credentials=True,  # Разрешение на передачу cookies
    allow_methods=["*"],  # Разрешение всех HTTP-методов (GET, POST, PUT, DELETE и т.д.)
    allow_headers=["*"],  # Разрешение всех заголовков
)

# Конфигурация безопасности
SECRET_KEY = "your-secret-key-here"  # В реальном проекте используйте переменные окружения
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
LOGIN_ATTEMPTS_LIMIT = 5
LOGIN_BLOCK_TIME_MINUTES = 15

# "База данных" в виде словаря, где ключ - email пользователя, а значение - данные пользователя
# users: Dict[str, dict] = {}
users = get_dict_users()
login_attempts = {}  # Временное хранилище попыток входа


# Функция для генерации 6-значного кода верификации
def generate_verification_code() -> str:
    """
    Генерирует случайный 6-значный код.
    Возвращает строку с ведущими нулями, если число меньше 6 цифр.
    """
    code = f"{random.randint(0, 999999):06d}"  # Генерация числа от 0 до 999999, форматирование до 6 цифр
    return code


# Функция для вывода кода верификации в терминал (для разработки)
def print_verification_code(email: str, code: str):
    """
    Выводит код верификации в терминал в красивом формате.
    Используется только для разработки.
    """
    print("\n" + "═" * 50)  # Разделитель
    print(f"📧 Получатель: \033[1;34m{email}\033[0m")  # Email пользователя (синий цвет)
    print(f"🔢 Код верификации: \033[1;32m{code}\033[0m")  # Код верификации (зеленый цвет)
    print("═" * 50 + "\n")  # Разделитель


# Функция для обновления юзера в соответствии с базой данных
def update_users():
    global users
    users = get_dict_users()


def check_nickname(nickname):
    for i in users:
        if nickname == i['nickname']:
            return True
    return False


# Модели запросов для валидации входных данных
class TokenData(BaseModel):
    email: str
    exp: datetime


class LoginRequest(BaseModel):
    """
    Модель для запроса на вход (логин).
    Поля:
    - email: Email пользователя
    - password: Пароль пользователя
    """
    email: str
    password: str


class RegisterRequest(BaseModel):
    """
    Модель для запроса на регистрацию.
    Поля:
    - email: Email пользователя (валидируется как EmailStr)
    - password: Пароль пользователя
    - nickname: Никнейм пользователя
    """
    email: EmailStr
    password: str
    nickname: str


class VerifyRequest(BaseModel):
    """
    Модель для запроса на верификацию email.
    Поля:
    - email: Email пользователя
    - code: Код верификации
    """
    email: EmailStr
    code: str


class RecoverRequest(BaseModel):
    """
    Модель для запроса на восстановление пароля.
    Поля:
    - email: Email пользователя
    """
    email: EmailStr


class RecoverVerifyRequest(BaseModel):
    """
    Модель для запроса на проверку кода восстановления.
    Поля:
    - email: Email пользователя
    - code: Код восстановления
    """
    email: EmailStr
    code: str


class ChangePasswordRequest(BaseModel):
    """
    Модель для запроса на смену пароля.
    Поля:
    - email: Email пользователя
    - code: Код восстановления
    - password: Новый пароль
    """
    email: EmailStr
    code: str
    password: str


class CodeType(str, Enum):
    """
    Перечисление типов кодов:
    - VERIFICATION: Код для верификации email
    - RECOVERY: Код для восстановления пароля
    """
    VERIFICATION = "verification"
    RECOVERY = "recovery"


class ResendCodeRequest(BaseModel):
    """
    Модель для запроса на повторную отправку кода.
    Поля:
    - email: Email пользователя
    - code_type: Тип кода (verification или recovery)
    """
    email: EmailStr
    code_type: CodeType


# Генерация токена
def create_access_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": email, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise JWTError("Invalid token payload")
        return TokenData(email=email, exp=payload.get("exp"))
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token"},
            headers={"WWW-Authenticate": "Bearer"},
        )


# Проверка количества попыток входа
def check_login_attempts(email: str):
    if email in login_attempts:
        attempts, block_time = login_attempts[email]
        if datetime.utcnow() < block_time:
            raise HTTPException(
                status_code=429,
                detail={"code": ErrorCodes.TOO_MANY_ATTEMPTS},
                headers={"Retry-After": str((block_time - datetime.utcnow()).seconds)},
            )
        if attempts >= LOGIN_ATTEMPTS_LIMIT:
            login_attempts[email] = (attempts, datetime.utcnow() + timedelta(minutes=LOGIN_BLOCK_TIME_MINUTES))
            raise HTTPException(
                status_code=429,
                detail={"code": ErrorCodes.TOO_MANY_ATTEMPTS},
                headers={"Retry-After": str(LOGIN_BLOCK_TIME_MINUTES * 60)},
            )


# Коды сообщений для локализации ошибок и успешных операций
class ErrorCodes:
    """
    Класс с кодами ошибок и сообщений.
    Используется для стандартизации ответов API.
    """
    ALREADY_VERIFIED = 'already_verified'  # Аккаунт уже подтвержден
    SAVING_FAILED = 'saving_failed'  # Сохранение в базу данных не удалось
    NOT_ONE_EMAIL = 'not_one_email'  # Существуют пользователи с одинаковыми email
    USER_NOT_FOUND = "user_not_found"  # Пользователь не найден
    INVALID_CREDENTIALS = "invalid_credentials"  # Неверные учетные данные
    USER_EXISTS = "user_exists"  # Пользователь уже существует
    NICKNAME_EXISTS = 'nickname_exist'  # Этот ник уже занят
    INVALID_VERIFICATION_CODE = "invalid_verification_code"  # Неверный код верификации
    ACCOUNT_NOT_VERIFIED = "account_not_verified"  # Аккаунт не верифицирован
    PASSWORD_CHANGE_SUCCESS = "password_change_success"  # Пароль успешно изменен
    VERIFICATION_CODE_SENT = "verification_code_sent"  # Код верификации отправлен
    REGISTRATION_SUCCESS = "registration_success"  # Регистрация успешна
    VERIFICATION_SUCCESS = "verification_success"  # Верификация успешна
    TOO_MANY_ATTEMPTS = "too_many_attempts"  # Много попыток входа


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in ["/auth/login", "/auth/register", "/auth/verify",
                            "/auth/recover", "/auth/recover/verify", "/docs", "/openapi.json"]:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "missing_token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ")[1]  # Извлекает JWT токен
    try:
        token_data = verify_token(token)  # Проверяет его валидность
        request.state.user_email = token_data.email  # Сохраняет email пользователя в request.state для использования в обработчиках
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


# Обработчик для входа (логина)
@app.post("/auth/login")
def login(data: LoginRequest):
    """
    Обрабатывает запрос на вход.
    Проверяет email, пароль и статус верификации пользователя.
    """
    print(users)
    if data.email not in users:
        login_attempts[data.email] = (login_attempts.get(data.email, (0, datetime.min))[0] + 1, datetime.min)
        # Если пользователь не найден, возвращаем ошибку 404
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCodes.USER_NOT_FOUND}
        )

    user = users[data.email]  # Получаем данные пользователя
    if not verify_password(data.password, user["password"]):
        login_attempts[data.email] = (login_attempts.get(data.email, (0, datetime.min))[0] + 1, datetime.min)
        # Если пароль неверный, возвращаем ошибку 401
        raise HTTPException(
            status_code=401,
            detail={"code": ErrorCodes.INVALID_CREDENTIALS}
        )

    if not user["verified"]:
        # Если аккаунт не верифицирован, возвращаем ошибку 403
        raise HTTPException(
            status_code=403,
            detail={"code": ErrorCodes.ACCOUNT_NOT_VERIFIED}
        )

    if data.email in login_attempts:
        del login_attempts[data.email]

    # Возвращаем токен при успешной авторизации
    return {"token": create_access_token(data.email)}


# Обработчик для регистрации
@app.post("/auth/register")
def register(data: RegisterRequest):
    """
    Обрабатывает запрос на регистрацию.
    Создает нового пользователя и отправляет код верификации.
    """
    # Валидация пароля
    password_error = validate_password(data.password)
    if password_error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_password", "message": password_error}
        )

    if data.email in users:
        # Если пользователь уже существует, возвращаем ошибку 400
        raise HTTPException(
            status_code=400,
            detail={"code": ErrorCodes.USER_EXISTS}
        )

    if check_nickname(data.nickname):
        # Если этот ник уже занят, возвращаем ошибку 400
        raise HTTPException(
            status_code=400,
            detail={"code": ErrorCodes.NICKNAME_EXISTS}
        )

    # Генерируем код верификации
    verification_code = generate_verification_code()

    # Сохраняем данные пользователя в "базу данных"
    trace_back = save_user(data.email, data.password, data.nickname, False, verification_code)
    if trace_back != 'success':
        raise HTTPException(
            # справить код ошибки
            status_code=500,
            detail={"code": ErrorCodes.SAVING_FAILED}
        )

    # Обновляем список юзеров
    update_users()
    # Выводим код верификации в терминал
    print_verification_code(str(data.email), verification_code)

    # Возвращаем сообщение об успешной регистрации
    return {
        "message": {"code": ErrorCodes.REGISTRATION_SUCCESS},
        "verification_code": verification_code  # Только для разработки
    }


# Обработчик для верификации email
@app.post("/auth/verify")
def verify(data: VerifyRequest):
    """
    Обрабатывает запрос на верификацию email.
    Проверяет код верификации и активирует аккаунт.
    """
    if data.email not in users:
        # Если пользователь не найден, возвращаем ошибку 404
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCodes.USER_NOT_FOUND}
        )
    user = users[data.email]

    if data.code != user["verification_code"]:
        # Если код неверный, возвращаем ошибку 400
        raise HTTPException(
            status_code=400,
            detail={"code": ErrorCodes.INVALID_VERIFICATION_CODE}
        )
    # Активируем аккаунт
    trace_back = change_db_users(user['email'], (('verified', 1)))
    if trace_back != 'success':
        raise HTTPException(
            # справить код ошибки
            status_code=500,
            detail={"code": ErrorCodes.SAVING_FAILED}
        )
    update_users()
    return {
        "token": create_access_token(user['email']),
        "message": {"code": ErrorCodes.VERIFICATION_SUCCESS}
    }


# Обработчик для восстановления пароля
@app.post("/auth/recover")
def recover(data: RecoverRequest):
    """
    Обрабатывает запрос на восстановление пароля.
    Отправляет код восстановления на email.
    """

    if data.email not in users:
        # Если пользователь не найден, возвращаем ошибку 404
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCodes.USER_NOT_FOUND}
        )

    user = users[data.email]
    # Генерируем код восстановления
    verification_code = generate_verification_code()
    trace_back = change_db_users(user['email'], (('verified', 1), ('password', data.password)))
    if trace_back != 'success':
        raise HTTPException(
            # справить код ошибки
            status_code=500,
            detail={"code": ErrorCodes.SAVING_FAILED}
        )

    update_users()
    # Выводим код восстановления в терминал
    print_verification_code(user['email'], verification_code)

    # Возвращаем сообщение об успешной отправке кода
    return {
        "message": {"code": ErrorCodes.VERIFICATION_CODE_SENT},
    }


# Обработчик для проверки кода восстановления
@app.post("/auth/recover/verify")
def recover_verify(data: RecoverVerifyRequest):
    """
    Обрабатывает запрос на проверку кода восстановления.
    """
    if data.email not in users:
        # Если пользователь не найден, возвращаем ошибку 404
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCodes.USER_NOT_FOUND}
        )
    user = users[data.email]
    if data.code != user["verification_code"]:
        # Если код неверный, возвращаем ошибку 400
        raise HTTPException(
            status_code=400,
            detail={"code": ErrorCodes.INVALID_VERIFICATION_CODE}
        )
    trace_back = change_db_users(user['email'], (('verified', 1)))
    if trace_back != 'success':
        raise HTTPException(
            # справить код ошибки
            status_code=500,
            detail={"code": ErrorCodes.SAVING_FAILED}
        )
    update_users()
    return {"message": {"code": "recovery_verified"}}


# Обработчик для смены пароля
@app.post("/auth/recover/change")
def change_password(data: ChangePasswordRequest):
    """
    Обрабатывает запрос на смену пароля.
    Проверяет код восстановления и обновляет пароль.
    """
    if data.email not in users:
        # Если пользователь не найден, возвращаем ошибку 404
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCodes.USER_NOT_FOUND}
        )
    user = users[data.email]
    if data.code != user["verification_code"]:
        # Если код неверный, возвращаем ошибку 400
        raise HTTPException(
            status_code=400,
            detail={"code": ErrorCodes.INVALID_VERIFICATION_CODE}
        )
    # Устанавливаем статус verified
    trace_back = change_db_users(user['email'], (('verified', 1)))
    if trace_back != 'success':
        raise HTTPException(
            # справить код ошибки
            status_code=500,
            detail={"code": ErrorCodes.SAVING_FAILED}
        )

    # Обновляем пароль
    trace_back = change_db_users(user['email'], (('password', data.password)))
    if trace_back != 'success':
        raise HTTPException(
            # справить код ошибки
            status_code=500,
            detail={"code": ErrorCodes.SAVING_FAILED}
        )
    update_users()
    return {
        "token": create_access_token(user['email']),
        "message": {"code": ErrorCodes.PASSWORD_CHANGE_SUCCESS}
    }


# Обработчик для повторной отправки кода
@app.post("/auth/verify/resend")
def resend_code(data: ResendCodeRequest):
    """
    Обрабатывает запрос на повторную отправку кода.
    Генерирует новый код и отправляет его на email.
    """
    if data.email not in users:
        # Если пользователь не найден, возвращаем ошибку 404
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCodes.USER_NOT_FOUND}
        )
    user = users[data.email]
    if data.code_type == CodeType.VERIFICATION:
        if user["verified"]:
            # Если аккаунт уже верифицирован, возвращаем ошибку 400
            raise HTTPException(
                status_code=400,
                detail={"code": ErrorCodes.ALREADY_VERIFIED}
            )

    # Генерируем новый код
    new_code = generate_verification_code()
    trace_back = change_db_users(user['email'], (('verification_code', new_code)))
    if trace_back != 'success':
        raise HTTPException(
            # справить код ошибки
            status_code=500,
            detail={"code": ErrorCodes.SAVING_FAILED}
        )

    update_users()
    # Выводим новый код в терминал
    print_verification_code(user['email'], new_code)

    # Возвращаем сообщение об успешной отправке кода
    return {
        "message": {"code": ErrorCodes.VERIFICATION_CODE_SENT},
    }


@app.get('/api/leaderboard')
def leaderboard():
    info = get_leaderboard(len(users))
    print(info)
    return info


# Точка входа в приложение
if __name__ == "__main__":
    # Запускаем приложение на хосте 0.0.0.0 и порту 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
