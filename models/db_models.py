from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, ForeignKey, Enum, Float, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)
    username = Column(String)
    verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    achievement = Column(String, default='0')
    avatar = Column(String, default='0')


class Test(Base):
    __tablename__ = 'tests'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    topics = Column(JSON)
    time_limit = Column(Integer)  # Общее время теста в секундах


class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'))
    text = Column(String)
    type = Column(Enum('choice', 'open', 'order', name='question_type'))
    options = Column(JSON)
    correct_answer = Column(JSON)
    explanation = Column(String, nullable=True)
    time_limit = Column(Integer)


class UserTestSession(Base):
    __tablename__ = 'user_test_sessions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    score = Column(Integer, nullable=True)
    status = Column(String)


class Fundamentals(Base):
    __tablename__ = 'fundamentals'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    score = Column(Integer, default=0)
    testsPassed = Column(Integer, default=0)
    totalTests = Column(Integer, default=0)
    lastActivity = Column(DateTime)


class Algorithms(Base):
    __tablename__ = 'algorithms'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    score = Column(Integer, default=0)
    testsPassed = Column(Integer, default=0)
    totalTests = Column(Integer, default=0)
    lastActivity = Column(DateTime)


class UserAnswer(Base):
    __tablename__ = 'user_answers'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    question_id = Column(Integer, ForeignKey('questions.id'))
    given_answer = Column(JSON)
    is_correct = Column(Boolean)
    response_time = Column(Float)


class UserSuggestion(Base):
    __tablename__ = 'user_suggestions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    question_data = Column(JSON)  # Будем хранить ВСЕ данные здесь
    status = Column(String, default='pending')  # Просто строка без Enum


class Achievement(Base):
    __tablename__ = 'achievements'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    name = Column(String, index=True)  # Например: 'first_contribution', 'perfect_score'
    title = Column(String)  # 'Знаток алгоритмов'
    description = Column(String)  # 'Правильно ответил на 100 вопросов'
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    icon = Column(String)  # URL иконки


class AchievementTemplate(Base):
    __tablename__ = "achievement_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)  # Техническое имя (например, "first_test_passed")
    title = Column(String)              # "Первый тест пройден"
    description = Column(String)        # "Поздравляем! Вы прошли первый тест."
    icon = Column(String)