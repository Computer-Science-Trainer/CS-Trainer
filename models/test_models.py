from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any, Union


class QuestionCreate(BaseModel):
    title: str
    question_text: str
    question_type: Literal['single-choice', 'multiple-choice', 'open-ended', 'ordering']
    difficulty: Literal['easy', 'medium', 'hard']
    options: List[str]
    correct_answer: Union[str, List[str]]
    topic_code: str
    terms_accepted: bool


class TestCreate(BaseModel):
    title: str
    topics: List[str]
    questions: List[QuestionCreate]
    time_limit: Optional[int] = None
    section: Literal['fundamentals', 'algorithms']


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


class ExamConfig(BaseModel):
    question_count: int = 2
    time_limit: int = 3600
    topic: str


class QuestionAnswer(BaseModel):
    question_id: int
    answer: Union[str, Dict]
    response_time: float
    
    
class QuestionFilter(BaseModel):
    topics: Optional[List[str]] = None
    include_wrong: bool = False  # Включить вопросы с ошибками
    skip: int = 0
    limit: int = 20


class SuggestionStatusUpdate(BaseModel):
    status: Literal['approved', 'rejected']
    comment: Optional[str] = None


class TestStats(BaseModel):
    test_id: int
    attempts: int
    best_score: float
    average_score: float
