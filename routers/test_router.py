from fastapi import APIRouter, Depends, HTTPException
from models.test_models import TestCreate, TestUpdate, QuestionCreate
from services.test_service import (
    create_test,
    get_test,
    update_test,
    start_test_session,
    submit_test_answers,
    submit_exam_answers,
    get_user_suggestions,
    get_topic_stats,
    get_user_stats,
    generate_exam,
    get_questions_by_filter
)
from routers.user_router import UserOut
from database import SessionLocal
from datetime import datetime
from models.db_models import Question, UserSuggestion, Topic
from models.schemas import SuggestionOut
from models.test_models import ExamConfig, SuggestionStatusUpdate, QuestionFilter
from security import decode_access_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models.schemas import QuestionOut, SuggestionOut


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = decode_access_token(credentials.credentials)
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        from services.user_service import get_user_by_email
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


async def get_admin_user(user: dict = Depends(get_current_user)):
    from services.admin_service import is_user_admin
    if not is_user_admin(user["id"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

router = APIRouter(prefix="/api/tests")


@router.post("/")
async def create_new_test(test_data: TestCreate, user: UserOut = Depends(get_current_user), db: Session = Depends(get_db)):
    for topic in test_data.topics:
        if not db.query(Topic).filter(Topic.code == topic).first():
            raise HTTPException(status_code=400, detail=f"Topic {topic} not found")

    for question in test_data.questions:
        if not db.query(Topic).filter(Topic.code == question.topic_code).first():
            raise HTTPException(status_code=400, detail=f"Topic {question.topic_code} not found")

    return create_test(test_data, user.id)


@router.put("/{test_id}")
async def update_test_endpoint(test_id: int, test_data: TestUpdate, user=Depends(get_current_user)):
    return update_test(test_id, test_data, user.id)


@router.get("/{test_id}/randomized")
async def get_randomized_test(test_id: int):
    return get_test(test_id, randomized=True)


@router.post("/{test_id}/start")
async def start_test(test_id: int, user=Depends(get_current_user)):
    return start_test_session(test_id, user.id)


@router.post("/{test_id}/submit")
async def submit_test(test_id: int, answers: dict, user=Depends(get_current_user)):
    return submit_test_answers(test_id, user.id, answers)


@router.get("/users/{user_id}/stats")
async def get_user_statistics(user_id: int):
    return get_user_stats(user_id)


@router.get("/questions/{question_id}", response_model=QuestionOut)
async def get_question_by_id(
        question_id: int,
        user: UserOut = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "id": question.id,
        "title": question.title,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "options": question.options,
        "topic_code": question.topic_code,
        "created_at": question.created_at
    }


@router.get("/wrong_answers")
async def get_wrong_answers(
    user: UserOut = Depends(get_current_user),
    skip: int = 0,
    limit: int = 10
):
    """Вопросы с неправильными ответами"""
    filters = QuestionFilter(include_wrong=True, skip=skip, limit=limit)
    return get_questions_by_filter(user.id, filters)


@router.post("/exam/start")
async def start_exam(
    config: ExamConfig,
    user: UserOut = Depends(get_current_user)
):
    return generate_exam(user.id, config)


@router.post("/exam/{session_id}/submit")
async def submit_exam(
    session_id: int,
    answers: dict,
    user: UserOut = Depends(get_current_user)
):
    try:
        return submit_exam_answers(session_id, user.id, answers)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/stats/topics")
async def get_topic_statistics(
    user: UserOut = Depends(get_current_user)
):
    """Статистика по ошибкам в разрезе тем"""
    return get_topic_stats(user.id)


@router.get("/questions/by-topic/{topic_code}", response_model=List[QuestionOut])
async def get_questions_by_topic(
    topic_code: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    questions = db.query(Question).filter(
        Question.topic_code == topic_code
    ).limit(limit).all()
    return format_questions_response(questions)


@router.post("/questions/", response_model=QuestionOut)
async def create_question(
    question: QuestionCreate,
    user: UserOut = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Проверка существования темы
    topic = db.query(Topic).filter(Topic.code == question.topic_code).first()
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic {question.topic_code} not found")

    # Валидация correct_answer в зависимости от типа вопроса
    if question.question_type in ['multiple-choice', 'ordering']:
        if not isinstance(question.correct_answer, list):
            raise HTTPException(
                status_code=400,
                detail=f"For {question.question_type}, correct_answer must be a list"
            )
        if question.question_type == 'multiple-choice' and len(question.correct_answer) < 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple-choice questions must have at least one correct answer"
            )
    elif question.question_type in ['single-choice', 'open-ended']:
        if not isinstance(question.correct_answer, str):
            raise HTTPException(
                status_code=400,
                detail=f"For {question.question_type}, correct_answer must be a string"
            )

    # Проверка options для вопросов с вариантами ответов
    if question.question_type in ['single-choice', 'multiple-choice', 'ordering']:
        if not question.options or len(question.options) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"{question.question_type} questions must have at least 2 options"
            )

    # Создание вопроса в БД
    try:
        db_question = Question(
            title=question.title,
            question_text=question.question_text,
            question_type=question.question_type,
            difficulty=question.difficulty,
            options=question.options,
            correct_answer=question.correct_answer,
            topic_code=question.topic_code,
            proposer_id=user.id,
            created_at=datetime.utcnow(),
            terms_accepted=question.terms_accepted
        )

        db.add(db_question)
        db.commit()
        db.refresh(db_question)

        # Формируем ответ
        return {
            "id": db_question.id,
            "title": db_question.title,
            "question_text": db_question.question_text,
            "question_type": db_question.question_type,
            "difficulty": db_question.difficulty,
            "options": db_question.options,
            "correct_answer": db_question.correct_answer,
            "topic_code": db_question.topic_code,
            "created_at": db_question.created_at
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating question: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating the question"
        )


# Для предложений вопросов
@router.post("/suggestions", response_model=SuggestionOut)
async def create_suggestion(
        suggestion: QuestionCreate,
        user: UserOut = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    new_suggestion = UserSuggestion(
        user_id=user.id,
        question_data={
            "title": suggestion.title,
            "question_text": suggestion.question_text,
            "question_type": suggestion.question_type,
            "options": suggestion.options,
            "correct_answer": suggestion.correct_answer,
            "topic_code": suggestion.topic_code
        },
        status="pending"
    )
    db.add(new_suggestion)
    db.commit()
    return format_suggestion_response(new_suggestion.id)


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionOut)
async def get_suggestion(
        suggestion_id: int,
        db: Session = Depends(get_db)
):
    """Получение предложения по ID"""
    suggestion = db.query(UserSuggestion).get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Предложение не найдено")

    return {
        "id": suggestion.id,
        "user_id": suggestion.user_id,
        "title": suggestion.question_data.get("title"),
        "question_text": suggestion.question_data.get("question_text"),
        "question_type": suggestion.question_data.get("question_type"),
        "options": suggestion.question_data.get("options", []),
        "correct_answer": suggestion.question_data.get("correct_answer"),
        "topic_code": suggestion.question_data.get("topic_code"),
        "status": suggestion.status,
        "created_at": suggestion.created_at,
        "admin_comment": suggestion.admin_comment
    }


@router.get("/suggestions/my")
async def get_my_suggestions(
        user: UserOut = Depends(get_current_user)
):
    """Получить мои предложенные вопросы"""
    return get_user_suggestions(user.id)


# Для модерации (только админы)
@router.put("/suggestions/{suggestion_id}")
async def update_suggestion_status(
        suggestion_id: int,
        update: SuggestionStatusUpdate,
        admin: dict = Depends(get_admin_user),
        db: Session = Depends(get_db)
):
    """Обновление статуса предложения (админ)"""
    suggestion = db.query(UserSuggestion).get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Предложение не найдено")

    suggestion.status = update.status
    suggestion.admin_comment = update.comment

    if update.status == 'approved':
        # Создаем вопрос на основе предложения
        new_question = Question(
            title=suggestion.question_data['title'],
            question_text=suggestion.question_data['question_text'],
            question_type=suggestion.question_data['question_type'],
            difficulty=suggestion.question_data.get('difficulty', 'medium'),
            options=suggestion.question_data.get('options', []),
            correct_answer=suggestion.question_data['correct_answer'],
            sample_answer=suggestion.question_data.get('sample_answer'),
            terms_accepted=True,
            topic_code=suggestion.question_data['topic_code'],
            proposer_id=suggestion.user_id,
            created_at=datetime.utcnow()
        )
        db.add(new_question)

    db.commit()
    return {"status": "success"}
        
        
def format_questions_response(questions):
    return [{
        "id": q.id,
        "title": q.title,
        "question_text": q.question_text,
        "question_type": q.question_type,
        "difficulty": q.difficulty,
        "options": q.options,
        "topic_code": q.topic_code
    } for q in questions]


def format_suggestion_response(suggestion_id):
    db = SessionLocal()
    try:
        suggestion = db.query(UserSuggestion).get(suggestion_id)
        return {
            "id": suggestion.id,
            "user_id": suggestion.user_id,
            "title": suggestion.question_data.get("title"),
            "question_text": suggestion.question_data.get("question_text"),
            "question_type": suggestion.question_data.get("question_type"),
            "options": suggestion.question_data.get("options", []),
            "correct_answer": suggestion.question_data.get("correct_answer"),
            "topic_code": suggestion.question_data.get("topic_code"),
            "status": suggestion.status,
            "created_at": suggestion.created_at,
            "admin_comment": suggestion.admin_comment
        }
    finally:
        db.close()
