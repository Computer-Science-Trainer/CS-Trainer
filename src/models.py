from src import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)  # Логин пользователя
    username = db.Column(db.String(64), unique=True, nullable=True)  # Имя пользователя
    password_hash = db.Column(db.String(128), nullable=False)  # Хеш пароля
    description = db.Column(db.String(256))  # Описание пользователя
    avatar = db.Column(db.String(256), default='default_avatar.png')  # Путь к аватарке (по умолчанию 'default_avatar.png')
    reset_token = db.Column(db.String(128))  # Токен для восстановления пароля

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self):
        self.reset_token = os.urandom(16).hex()  # Генерация случайного токена
        return self.reset_token


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)  # Текст вопроса
    category = db.Column(db.String(64), nullable=False)  # Категория вопроса (фи, аисд)
    correct_answer = db.Column(db.String(256), nullable=False)  # Правильный ответ на вопрос


class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(64), nullable=False)  # Кто ответил
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)  # Ссылка на вопрос
    user_answer = db.Column(db.String(256), nullable=False)  # Ответ пользователя
    is_correct = db.Column(db.Boolean, default=False)  # Правильный ли ответ
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # Дата создания ответа