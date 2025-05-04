from sqlalchemy.orm import Session
from database import SessionLocal
from models.db_models import Fundamentals, Algorithms, User
from datetime import datetime
import bcrypt


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def get_user_by_email(email: str) -> dict | None:
    if not isinstance(email, str):
        raise ValueError("Email must be a string")
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None

        return {
            'id': user.id,
            'email': user.email,
            'password': user.password,
            'username': user.username,
            'verified': user.verified,
            'verification_code': user.verification_code
        }
    finally:
        db.close()


def save_user(email: str, password: str, username: str, verified: bool, verification_code: str) -> str:
    db = SessionLocal()
    try:
        # Проверяем, существует ли пользователь
        if db.query(User).filter(User.email == email).first():
            return 'user_exists'

        # Создаем нового пользователя
        user = User(
            email=email,
            password=password,
            username=username,
            verified=verified,
            verification_code=verification_code,

        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Создаем связанные записи в fundamentals и algorithms
        now = datetime.now()

        fundamentals = Fundamentals(
            user_id=user.id,
            score=0,
            testsPassed=0,
            totalTests=0,
            lastActivity=now
        )

        algorithms = Algorithms(
            user_id=user.id,
            score=0,
            testsPassed=0,
            totalTests=0,
            lastActivity=now
        )

        db.add(fundamentals)
        db.add(algorithms)
        db.commit()

        return 'success'
    except Exception as e:
        db.rollback()
        print(f"Error saving user: {str(e)}")
        return 'error'
    finally:
        db.close()


def change_db_users(email: str, *updates: tuple[str, any]) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return 'user_not_found'

        for column, value in updates:
            setattr(user, column, value)

        db.commit()
        return 'success'
    except Exception as e:
        db.rollback()
        print(f"Error updating user: {str(e)}")
        return 'error'
    finally:
        db.close()


def update_user_achievements(user_id: int):
    #ачивки доделать
    pass
