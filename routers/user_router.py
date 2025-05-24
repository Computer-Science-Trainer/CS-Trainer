from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from services.user_service import get_user_by_email, get_user_by_username, get_user_tests, get_user_scores
from services.user_service import get_user_by_id, save_user_test
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


class TestStartIn(BaseModel):
    section: str
    topics: List[str]


class TestStartOut(BaseModel):
    id: int


@router.post("/tests", response_model=TestStartOut, status_code=201)
def start_test(body: TestStartIn, authorization: str = Header(
        None, alias="Authorization")):
    # authorize user
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
    # map topic labels to IDs
    labels = body.topics or []
    if labels:
        placeholders = ",".join(["%s"] * len(labels))
        rows = execute(
            f"SELECT id FROM topics WHERE label IN ({placeholders})",
            tuple(labels))
        topic_ids = [r[0] for r in rows]
    else:
        topic_ids = []
    # map section code to DB value
    section_map = {"FI": "fundamentals", "AS": "algorithms"}
    db_section = section_map.get(body.section)
    if not db_section:
        raise HTTPException(
            status_code=400, detail={
                "code": "invalid_section"})
    # insert initial test record
    save_user_test(user_id, "practice", db_section, 0, 0, topic_ids)
    # retrieve new test ID
    row = execute(
        "SELECT id FROM tests WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
        (user_id,), fetchone=True
    )
    test_id = row[0]
    return {"id": test_id}


@router.get("/tests/{test_id}", response_model=QuestionsWithEndOut)
def get_test_questions(test_id: int, authorization: str = Header(
        None, alias="Authorization")):
    # authorize user
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
    # fetch test topics
    row = execute(
        "SELECT topics, questions, created_at FROM tests WHERE id = %s AND user_id = %s",
        (test_id, user_id), fetchone=True
    )
    if not row:
        raise HTTPException(status_code=404, detail={"code": "test_not_found"})
    topic_ids = json.loads(row[0]) or []
    questions_json = row[1]
    created_at = row[2]
    # If questions were already saved and not empty, return them
    if questions_json:
        question_ids = json.loads(questions_json)
        if question_ids:
            questions = []
            topics = []
            # load saved question details
            placeholders = ",".join(["%s"] * len(question_ids))
            rows = execute(
                f"SELECT id, title, question_text, question_type, difficulty, options "
                f"FROM current_questions WHERE id IN ({placeholders})",
                tuple(question_ids)
            )
            id_to_row = {r[0]: r for r in rows}
            for qid in question_ids:
                r = id_to_row.get(qid)
                if r:
                    questions.append({
                        "id": r[0],
                        "title": r[1],
                        "question_text": r[2],
                        "question_type": r[3],
                        "difficulty": r[4],
                        "options": json.loads(r[5]) if r[5] else []
                    })
            # load topics labels
            topics_row = execute(
                "SELECT topics FROM tests WHERE id = %s",
                (test_id,),
                fetchone=True
            )
            if topics_row and topics_row[0]:
                topic_ids_db = json.loads(topics_row[0])
                if topic_ids_db:
                    placeholders = ",".join(["%s"] * len(topic_ids_db))
                    topic_labels_rows = execute(
                        f"SELECT label FROM topics WHERE id IN ({placeholders})",
                        tuple(topic_ids_db)
                    )
                    topics = [r[0] for r in topic_labels_rows]
            # load test metadata
            end_time_row = execute(
                "SELECT end_time, passed, total, average, earned_score, section, created_at "
                "FROM tests WHERE id = %s",
                (test_id,),
                fetchone=True
            )
            if end_time_row and end_time_row[0] is not None:
                end_time, passed, total, average, earned_score, section, created_at_db = end_time_row
            else:
                end_time = created_at
                passed = total = average = earned_score = 0
                section = ""
                created_at_db = created_at
            return {
                "questions": questions,
                "end_time": end_time,
                "start_time": created_at,
                "id": test_id,
                "type": "custom",
                "section": section or "",
                "passed": passed,
                "total": total,
                "average": average,
                "topics": topics,
                "created_at": (
                    created_at_db.isoformat()
                    if created_at_db else datetime.datetime.now(datetime.timezone.utc).isoformat()
                ),
                "earned_score": earned_score
            }
    # select exactly 10 questions: sample topic-specific then fill remainder
    if topic_ids:
        placeholders = ",".join(["%s"] * len(topic_ids))
        label_rows = execute(
            f"SELECT label FROM topics WHERE id IN ({placeholders})",
            tuple(topic_ids)
        )
        labels = [r[0] for r in label_rows]
        if not labels:
            raise HTTPException(
                status_code=404,
                detail={"code": "no_topics_found"}
            )
        placeholders2 = ",".join(["%s"] * len(labels))
        all_topic_qs = execute(
            f"SELECT id, title, question_text, question_type, difficulty, options "
            f"FROM current_questions WHERE topic_code IN ({placeholders2})",
            tuple(labels)
        )
        if len(all_topic_qs) >= 10:
            rows = random.sample(all_topic_qs, 10)
        else:
            selected = list(all_topic_qs)
            needed = 10 - len(selected)
            if selected:
                excl_ph = ",".join(["%s"] * len(selected))
                more = execute(
                    f"SELECT id, title, question_text, question_type, difficulty, options "
                    f"FROM current_questions WHERE id NOT IN ({excl_ph}) "
                    "ORDER BY RAND() LIMIT %s",
                    tuple([q[0] for q in selected]) + (needed,)
                )
            else:
                more = execute(
                    "SELECT id, title, question_text, question_type, difficulty, options "
                    "FROM current_questions ORDER BY RAND() LIMIT %s",
                    (needed,)
                )
            rows = selected + list(more)
    else:
        rows = execute(
            "SELECT id, title, question_text, question_type, difficulty, options "
            "FROM current_questions ORDER BY RAND() LIMIT 10"
        )
    questions = []
    for q_id, title, text, qtype, diff, opts_json in rows:
        questions.append({
            "id": q_id,
            "title": title,
            "question_text": text,
            "question_type": qtype,
            "difficulty": diff,
            "options": json.loads(opts_json) if opts_json else []
        })
    # calculate total duration and end time
    difficulty_map = {"easy": 1, "medium": 2, "hard": 5}
    total_minutes = sum(
        difficulty_map.get(q["difficulty"], 1)
        for q in questions
    )
    # set end_time to UTC+3 (Moscow time)
    moscow_tz = datetime.timezone(datetime.timedelta(hours=3))
    end_time = datetime.datetime.now(
        moscow_tz) + datetime.timedelta(minutes=total_minutes)
    # record selected questions into DB
    question_ids = [q["id"] for q in questions]
    execute(
        "UPDATE tests SET questions = %s WHERE id = %s",
        (json.dumps(question_ids), test_id)
    )
    # record end_time in DB (requires ALTER TABLE tests ADD COLUMN end_time
    # DATETIME)
    execute(
        "UPDATE tests SET end_time = %s WHERE id = %s",
        (end_time, test_id)
    )
    test_row = execute(
        "SELECT passed, total, average, earned_score, section, created_at, topics FROM tests WHERE id = %s",
        (test_id,
         ),
        fetchone=True)
    if test_row:
        passed, total, average, earned_score, section, created_at_db, topics_json = test_row
    else:
        # fallback values
        passed = total = average = earned_score = 0
        section = ""
        created_at_db = created_at
        topics_json = None
    # build topics list
    if topics_json:
        topic_ids_db = json.loads(topics_json)
        if topic_ids_db:
            placeholders = ",".join(["%s"] * len(topic_ids_db))
            topic_labels_rows = execute(
                f"SELECT label FROM topics WHERE id IN ({placeholders})",
                tuple(topic_ids_db)
            )
            topics = [r[0] for r in topic_labels_rows]
        else:
            topics = []
    else:
        topics = []
    return {
        "questions": questions,
        "end_time": end_time,
        "start_time": created_at,
        "id": test_id,
        "type": "custom",
        "section": section or "",
        "passed": passed,
        "total": total,
        "average": average,
        "topics": topics,
        "created_at": (
            created_at_db.isoformat()
            if created_at_db else datetime.datetime.now(datetime.timezone.utc).isoformat()
        ),
        "earned_score": earned_score
    }


@router.post("/tests/{test_id}/submit", response_model=TestResult)
def submit_test(test_id: int, body: TestSubmissionIn,
                authorization: str = Header(None, alias="Authorization")):
    # authorize user
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
    row = execute(
        "SELECT user_id, section, end_time FROM tests WHERE id = %s",
        (test_id,), fetchone=True
    )
    if not row:
        raise HTTPException(status_code=404, detail={"code": "test_not_found"})
    if row[0] != user_id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    section = row[1]
    end_time = row[2]
    now = datetime.datetime.now(datetime.timezone.utc)
    if end_time and now > end_time.replace(tzinfo=datetime.timezone.utc):
        test_row = execute(
            "SELECT passed, total, average, earned_score FROM tests WHERE id = %s",
            (test_id,
             ),
            fetchone=True)
        if test_row:
            passed, total, average, earned_score = test_row
        else:
            passed = total = average = earned_score = 0
        return TestResult(passed=passed, total=total,
                          average=average, earned_score=earned_score)
    # evaluate answers
    submitted = {ans.question_id: ans.answer for ans in body.answers}
    q_ids = list(submitted.keys())
    if not q_ids:
        raise HTTPException(
            status_code=400, detail={
                "code": "no_answers_provided"})
    # fetch correct answers with difficulty for scoring
    placeholders = ",".join(["%s"] * len(q_ids))
    rows = execute(
        f"SELECT id, correct_answer, difficulty FROM current_questions WHERE id IN ({placeholders})",
        tuple(q_ids)
    )
    passed = 0
    weighted_score = 0
    # scoring weights per difficulty
    weight_map = {'easy': 1, 'medium': 2, 'hard': 5}
    for qid, correct, difficulty in rows:
        user_ans = submitted.get(qid)
        correct_str = str(correct).strip() if correct is not None else ''
        user_ans_str = str(user_ans).strip() if user_ans is not None else ''
        if correct_str and user_ans_str and user_ans_str == correct_str:
            passed += 1
            weighted_score += weight_map.get(difficulty, 0)
    total = len(body.answers)
    average = passed / total if total else 0.0
    # update test record
    execute(
        "UPDATE tests SET passed = %s, total = %s, average = %s, earned_score = %s WHERE id = %s",
        (passed, total, average, weighted_score, test_id)
    )
    # update user section stats
    now = datetime.datetime.now(datetime.timezone.utc)
    table = 'fundamentals' if section == 'fundamentals' else 'algorithms'
    execute(
        f"UPDATE {table} SET score = score + %s, "
        f"testsPassed = testsPassed + %s, "
        f"totalTests = totalTests + %s, "
        f"lastActivity = %s WHERE user_id = %s",
        (weighted_score, passed, total, now, user_id)
    )
    moscow_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_moscow = datetime.datetime.now(moscow_tz)
    execute("UPDATE tests SET end_time = %s WHERE id = %s", (now_moscow, test_id))
    return TestResult(
        passed=passed,
        total=total,
        average=average,
        earned_score=weighted_score
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
