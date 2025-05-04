from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
# from database import Base
# from sqlalchemy import Column, Integer, String, JSON, Enum, Boolean, ForeignKey, DateTime, Float


class QuestionCreate(BaseModel):
    text: str
    type: Literal['choice', 'open', 'order']
    options: Optional[List[str]] = None
    correct_answer: Dict[str, Any]
    explanation: Optional[str] = None
    time_limit: Optional[int] = None


class TestCreate(BaseModel):
    title: str
    topics: List[str]
    questions: List[QuestionCreate]
    time_limit: Optional[int] = None


class TestUpdate(BaseModel):
    title: Optional[str] = None
    topics: Optional[List[str]] = None
    questions: Optional[List['QuestionCreate']] = None
    time_limit: Optional[int] = None


class UserAnswerSubmit(BaseModel):
    question_id: int
    given_answer: Dict[str, Any]
    response_time: float


class TestSubmit(BaseModel):
    answers: List[UserAnswerSubmit]


class QuestionFilter(BaseModel):
    topics: Optional[List[str]] = None
    # subject: Optional[Literal['fundamentals', 'algorithms']] = None
    # difficulty: Optional[int] = None
    include_wrong: Optional[bool] = False  # Включить вопросы с ошибками
    limit: Optional[int] = 20


class ExamConfig(BaseModel):
    question_count: int = 2
    time_limit: int = 3600


class QuestionSuggestion(BaseModel):
    text: str
    type: Literal['choice', 'open', 'order']
    options: Optional[List[str]] = None
    correct_answer: dict
    explanation: Optional[str] = None
    time_limit: Optional[int] = None


class SuggestionOut(BaseModel):
    id: int
    user_id: int
    question: QuestionSuggestion
    status: str
    created_at: str
    admin_comment: Optional[str]


class SuggestionStatusUpdate(BaseModel):
    status: Literal['approved', 'rejected']
    comment: Optional[str] = None


class AchievementOut(BaseModel):
    name: str
    title: str
    description: str
    unlocked_at: datetime
    icon: str
