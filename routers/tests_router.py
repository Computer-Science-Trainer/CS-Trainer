from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
import datetime

from security import decode_access_token
from jwt import ExpiredSignatureError, InvalidTokenError
from services.tests_service import start_test, get_test_questions, submit_test, get_test_answers

router = APIRouter()

# Request and response models


class TestStartIn(BaseModel):
    section: str
    topics: List[str]


class TestStartOut(BaseModel):
    id: int


class QuestionOut(BaseModel):
    id: int
    title: str
    question_text: str
    question_type: str
    difficulty: str
    options: List[str] = []


class QuestionsWithEndOut(BaseModel):
    questions: List[QuestionOut]
    end_time: datetime.datetime
    start_time: datetime.datetime
    id: int
    type: str
    section: str
    passed: Optional[int] = None
    total: Optional[int] = None
    average: Optional[float] = None
    topics: List[str] = []
    created_at: str
    earned_score: Optional[int] = None


class AnswerIn(BaseModel):
    question_id: int
    answer: str


class TestSubmissionIn(BaseModel):
    answers: List[AnswerIn]


class TestResult(BaseModel):
    passed: int
    total: int
    average: float
    earned_score: int

# Models for retrieving stored answers


class AnswerDetailOut(BaseModel):
    question_id: int
    question_type: str
    difficulty: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    points_awarded: int


class TestAnswersOut(BaseModel):
    answers: List[AnswerDetailOut]

# Authorization helper


def authorize(authorization: str) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    return user_id

# Routes


@router.post("/", response_model=TestStartOut, status_code=201)
def start_test_route(body: TestStartIn, authorization: str = Header(
        None, alias="Authorization")):
    user_id = authorize(authorization)
    test_id = start_test(user_id, body.section, body.topics)
    return {"id": test_id}


@router.get("/{test_id}", response_model=QuestionsWithEndOut)
def get_test_questions_route(
        test_id: int, authorization: str = Header(None, alias="Authorization")):
    user_id = authorize(authorization)
    return get_test_questions(user_id, test_id)


@router.post("/{test_id}/submit", response_model=TestResult)
def submit_test_route(test_id: int, body: TestSubmissionIn,
                      authorization: str = Header(None, alias="Authorization")):
    user_id = authorize(authorization)
    return submit_test(user_id, test_id, body.answers)


@router.get("/{test_id}/answers", response_model=TestAnswersOut)
def get_test_answers_route(
        test_id: int, authorization: str = Header(None, alias="Authorization")):
    user_id = authorize(authorization)
    return get_test_answers(user_id, test_id)
