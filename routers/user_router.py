from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from services.user_service import get_user_by_email, get_user_by_username, get_user_tests, get_user_scores
from services.user_service import get_user_by_id
from services.achievement_service import get_user_achievements
from security import decode_access_token
from jwt import ExpiredSignatureError, InvalidTokenError
from typing import List, Optional
import datetime
import json
from database import execute
from services.admin_service import is_user_admin
import random

router = APIRouter()


class UserOut(BaseModel):
    id: int
    email: str
    username: str


class AchievementOut(BaseModel):
    code: str
    emoji: str
    unlocked: bool
    unlocked_at: Optional[datetime.datetime] = None


class TestOut(BaseModel):
    id: int
    type: str
    section: str
    passed: int
    total: int
    average: float
    earned_score: int
    topics: List[str]
    created_at: datetime.datetime


class StatsOut(BaseModel):
    passed: int
    total: int
    average: float
    fundamentals: int
    algorithms: int


class ProfileUserOut(BaseModel):
    id: int
    username: str
    avatar: Optional[str] = None
    bio: Optional[str] = None
    telegram: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None


class QuestionOut(BaseModel):
    id: int
    title: str
    question_text: str
    question_type: str
    difficulty: str
    options: List[str] = []


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


class QuestionsWithEndOut(BaseModel):
    questions: List[QuestionOut]
    end_time: datetime.datetime
    start_time: datetime.datetime
    id: int
    type: str
    section: str
    passed: int | None = None
    total: int | None = None
    average: float | None = None
    topics: List[str] = []
    created_at: str
    earned_score: int | None = None


@router.get('/user/{username}', response_model=ProfileUserOut)
def get_profile_by_username(username: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "avatar": user.get("avatar"),
        "bio": user.get("bio"),
        "telegram": user.get("telegram"),
        "github": user.get("github"),
        "website": user.get("website"),
    }


@router.get('/user', response_model=ProfileUserOut)
def get_profile_by_id(id: int):
    """Return user profile by numeric ID via query param ?id=…"""
    user = get_user_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    return {
        "username": user.get("username"),
        "avatar": user.get("avatar"),
        "bio": user.get("bio"),
        "telegram": user.get("telegram"),
        "github": user.get("github"),
        "website": user.get("website"),
    }


@router.get("/me", response_model=UserOut)
def me(authorization: str = Header(None, alias="Authorization")):
    if (authorization and authorization.startswith("Bearer ")):
        token = authorization.split(" ", 1)[1]
    else:
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})

    return UserOut(
        id=user["id"], email=user["email"], username=user["username"]
    )


@router.get("/me/is_admin")
def check_is_admin(authorization: str = Header(None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})
    token = authorization.split(" ", 1)[1]
    from security import decode_access_token
    from jwt import ExpiredSignatureError, InvalidTokenError
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})
    is_admin = is_user_admin(user_id)
    if not is_admin:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    return {"is_admin": True}


@router.get("/users/{user_id}/achievements",
            response_model=List[AchievementOut])
def user_achievements_by_id(user_id: int):
    unlocked = get_user_achievements(user_id)
    return [
        {
            'code': a['code'],
            'emoji': a.get('emoji'),
            'unlocked': True,
            'unlocked_at': a['unlocked_at']
        }
        for a in unlocked
    ]


@router.get("/user/{username}/achievements",
            response_model=List[AchievementOut])
def user_achievements_by_username(username: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    return user_achievements_by_id(user['id'])


@router.get("/user/{username}/tests", response_model=List[TestOut])
def user_tests_by_username(username: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    return get_user_tests(user['id'])


@router.get("/user/{username}/stats", response_model=StatsOut)
def user_stats_by_username(username: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    tests = get_user_tests(user['id'])
    scores = get_user_scores(user['id'])
    if not tests:
        return StatsOut(
            passed=0,
            total=0,
            average=0.0,
            fundamentals=scores['fundamentals'],
            algorithms=scores['algorithms']
        )
    passed = sum(t['passed'] for t in tests)
    total = sum(t['total'] for t in tests)
    average = (
        sum(t['average'] for t in tests) / len(tests)
    ) if tests else 0.0
    return StatsOut(
        passed=passed,
        total=total,
        average=average,
        fundamentals=scores['fundamentals'],
        algorithms=scores['algorithms']
    )


@router.get("/user/{username}/recommendations", response_model=List[str])
def user_topic_recommendations(username: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found"})
    user_id = user["id"]
    tests = get_user_tests(user_id)
    topic_stats = {}
    topic_counts = {}
    for test in tests:
        if not test["topics"] or not test["total"]:
            continue
        for topic in test["topics"]:
            topic_stats.setdefault(topic, 0)
            topic_counts.setdefault(topic, 0)
            topic_stats[topic] += test["passed"] / test["total"]
            topic_counts[topic] += 1
    topic_averages = []
    for topic, total_score in topic_stats.items():
        avg = total_score / topic_counts[topic] if topic_counts[topic] else 0
        topic_averages.append((topic, avg))
    bad_topics = [t for t in topic_averages if t[1] < 0.99]
    if bad_topics:
        bad_topics.sort(key=lambda x: x[1])
        recommendations = [t[0] for t in bad_topics[:6]]
    else:
        rows = execute(
            "SELECT label FROM topics ORDER BY RAND() LIMIT 6"
        )
        recommendations = [r[0] for r in rows]
    return recommendations
