from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, ForeignKey, Float
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
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    type = Column(String(50), nullable=True)
    section = Column(String(50), nullable=False)
    passed = Column(Integer, default=0, nullable=False)
    total = Column(Integer, default=0, nullable=False)
    average = Column(Float, default=0.0, nullable=False)
    topics = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    earned_score = Column(Integer, default=0, nullable=False)


class Question(Base):
    __tablename__ = 'questions'
    iid = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=True)
    title = Column(String(255), nullable=False)
    question_text = Column(String(1000), nullable=False)
    question_type = Column(String(20), nullable=False)
    difficulty = Column(String(10), nullable=False)
    options = Column(JSON, nullable=True)
    correct_answer = Column(String(255), nullable=False)
    sample_answer = Column(String(1000), nullable=True)
    terms_accepted = Column(Boolean, default=False, nullable=False)
    topic_code = Column(String(50), nullable=False)
    proposer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    
    
class Fundamentals(Base):
    __tablename__ = 'fundamentals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    score = Column(Integer, default=0, nullable=False)
    testsPassed = Column(Integer, default=0, nullable=False)
    totalTests = Column(Integer, default=0, nullable=False)
    lastActivity = Column(DateTime, nullable=True)
    

class Algorithms(Base):
    __tablename__ = 'algorithms'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    score = Column(Integer, default=0, nullable=False)
    testsPassed = Column(Integer, default=0, nullable=False)
    totalTests = Column(Integer, default=0, nullable=False)
    lastActivity = Column(DateTime, nullable=True)


class UserTestSession(Base):
    __tablename__ = 'user_test_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=True)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)  # in_progress/completed/time_expired
    score = Column(Integer, nullable=True)
    time_limit = Column(Integer, nullable=True)
    exam_mode = Column(Boolean, default=False, nullable=False)
    

class UserSuggestion(Base):
    __tablename__ = 'user_suggestions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    question_data = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False)
    admin_comment = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    

class UserAchievement(Base):
    __tablename__ = 'user_achievements'
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    achievement_id = Column(Integer, ForeignKey('achievements.id'), nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Topic(Base):
    __tablename__ = 'topics'
    id = Column(Integer, primary_key=True)
    label = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False)
    section = Column(String(20), nullable=False)  # fundamentals/algorithms
    parent_id = Column(Integer, ForeignKey('topics.id'), nullable=True)


class UserAnswer(Base):
    __tablename__ = 'user_answers'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    given_answer = Column(JSON, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    response_time = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    test_session_id = Column(Integer, ForeignKey('user_test_sessions.id'), nullable=True)