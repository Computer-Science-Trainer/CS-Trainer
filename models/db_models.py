from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, ForeignKey, Float, JSON, DateTime
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    password = Column(String(255))
    username = Column(String(50))
    avatar = Column(String(255), nullable=True)
    verified = Column(Boolean, default=False)
    verification_code = Column(String(6))
    telegram = Column(String(50), nullable=True)
    github = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    bio = Column(String(500), nullable=True)
    refresh_token = Column(String(255), nullable=True)


class Test(Base):
    __tablename__ = 'tests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(String(50))
    section = Column(String(50))
    passed = Column(Integer)
    total = Column(Integer)
    average = Column(Float)
    topics = Column(JSON)
    created_at = Column(DateTime)
    earned_score = Column(Integer)


class Question(Base):
    __tablename__ = 'current_questions'
    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'))
    title = Column(String(255))
    question_text = Column(String(1000))
    question_type = Column(String(20))  # single-choice/open-ended
    difficulty = Column(String(10))     # easy/medium/hard
    options = Column(JSON)              # Варианты ответов
    correct_answer = Column(String(255))
    sample_answer = Column(String(1000), nullable=True)
    terms_accepted = Column(Boolean)
    topic_code = Column(String(50))
    proposer_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    
class Fundamentals(Base):
    __tablename__ = 'fundamentals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    score = Column(Integer)
    testsPassed = Column(Integer)
    totalTests = Column(Integer)
    lastActivity = Column(DateTime)
    

class Algorithms(Base):
    __tablename__ = 'algorithms'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    score = Column(Integer)
    testsPassed = Column(Integer)
    totalTests = Column(Integer)
    lastActivity = Column(DateTime)


class UserTestSession(Base):
    __tablename__ = 'user_test_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(20))  # in_progress/completed/time_expired
    score = Column(Integer, nullable=True)
    time_limit = Column(Integer, nullable=True)
    exam_mode = Column(Boolean, default=False)
    

class UserSuggestion(Base):
    __tablename__ = 'user_suggestions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    question_data = Column(JSON)
    status = Column(String(20))
    admin_comment = Column(String(500), nullable=True)
    created_at = Column(DateTime)
    

class UserAchievement(Base):
    __tablename__ = 'user_achievements'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    achievement_id = Column(Integer, ForeignKey('achievements.id'))
    unlocked_at = Column(DateTime)


class Topic(Base):
    __tablename__ = 'topics'
    id = Column(Integer, primary_key=True)
    label = Column(String(100))
    code = Column(String(20))
    section = Column(String(20))  # fundamentals/algorithms
    parent_id = Column(Integer, ForeignKey('topics.id'), nullable=True)


class UserAnswer(Base):
    __tablename__ = 'user_answers'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    question_id = Column(Integer, ForeignKey('questions.id'))
    given_answer = Column(JSON)
    is_correct = Column(Boolean)
    response_time = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    test_session_id = Column(Integer, ForeignKey('user_test_sessions.id'))