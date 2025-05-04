from fastapi import APIRouter, Depends, HTTPException
from models.test_models import TestCreate, TestUpdate, QuestionFilter, SuggestionOut
from services.test_service import (
    create_test,
    get_test,
    update_test,
    start_test_session,
    submit_test_answers,
    submit_question_suggestion,
    get_user_suggestions,
    get_user_stats,
    get_similar_questions,
    generate_exam,
    get_questions_by_filter
)
from security import get_current_user, get_admin_user
from models.schemas import UserOut
from database import SessionLocal
from models.db_models import Question
from models.test_models import ExamConfig, QuestionSuggestion, SuggestionStatusUpdate

router = APIRouter(prefix="/api/tests")


@router.post("/")
async def create_new_test(test_data: TestCreate, user: UserOut = Depends(get_current_user)):
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


@router.get("/questions/{question_id}")
async def get_question_by_id(
    question_id: int,
    user: UserOut = Depends(get_current_user)
):
    return get_question_detail(question_id)


@router.post("/filter")
async def get_filtered_questions(
    filters: QuestionFilter,
    skip: int = 0,
    limit: int = 20,
    user: UserOut = Depends(get_current_user)
):
    """Получение вопросов по фильтру"""
    return get_questions_by_filter(user.id, filters, skip, limit)


@router.get("/wrong_answers")
async def get_wrong_answers(
    user: UserOut = Depends(get_current_user),
    limit: int = 10
):
    """Вопросы с неправильными ответами"""
    filters = QuestionFilter(include_wrong=True, limit=limit)
    return get_questions_by_filter(user.id, filters)


@router.get("/similar/{question_id}")
async def get_similar_questions_endpoint(
        question_id: int,
        user: UserOut = Depends(get_current_user)
):
    """Похожие вопросы по topics исходного вопроса"""
    db = SessionLocal()
    try:
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        similar = db.query(Question).filter(
            Question.id != question_id,
            Question.topics.op('&&')(question.topics)  # Ищем вопросы с общими topics
        ).limit(5).all()

        return [{
            "id": q.id,
            "text": q.text,
            "type": q.type,
            "options": q.options
        } for q in similar]
    finally:
        db.close()


@router.get("/existing-questions")
async def get_existing_questions():
    db = SessionLocal()
    try:
        questions = db.query(Question).order_by(Question.id).limit(10).all()
        return [
            {
                "id": q.id,
                "text": q.text,
                "type": q.type,
                "options": q.options,
                "has_answer": bool(q.correct_answer)
            }
            for q in questions
        ]
    finally:
        db.close()


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
    return submit_test_answers(test_id=0, user_id=user.id, answers=answers, session_id=session_id)  # 0 для экзаменов


@router.get("/stats/topics")
async def get_topic_statistics(
    user: UserOut = Depends(get_current_user)
):
    """Статистика по ошибкам в разрезе тем"""
    return get_topic_stats(user.id)


# Для предложений вопросов
@router.post("/suggestions", response_model=SuggestionOut)
async def create_suggestion(
        suggestion: QuestionSuggestion,
        user: UserOut = Depends(get_current_user)
):
    """Создание предложения вопроса"""
    result = submit_question_suggestion(user.id, suggestion.dict())
    return format_suggestion_response(result["suggestion_id"])


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionOut)
async def get_suggestion(suggestion_id: int):
    """Получение предложения по ID"""
    return format_suggestion_response(suggestion_id)


def format_suggestion_response(suggestion_id: int):
    db = SessionLocal()
    try:
        suggestion = db.query(UserSuggestion).get(suggestion_id)
        if not suggestion:
            raise HTTPException(status_code=404, detail="Предложение не найдено")

        return {
            "id": suggestion.id,
            "user_id": suggestion.user_id,
            **suggestion.question_data,
            "status": suggestion.status
        }
    finally:
        db.close()


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
        admin: dict = Depends(get_admin_user)
):
    """Обновление статуса предложения (админ)"""
    user_id = admin["user_id"]
    db = SessionLocal()
    try:
        suggestion = db.query(UserSuggestion).get(suggestion_id)
        if not suggestion:
            raise HTTPException(status_code=404, detail="Предложение не найдено")

        suggestion.status = update.status
        suggestion.admin_comment = update.comment

        if update.status == 'approved':
            # Создаем вопрос на основе предложения
            new_question = Question(
                test_id=None,  # Пока не в тесте
                text=suggestion.question_data['text'],
                type=suggestion.question_data['type'],
                options=suggestion.question_data.get('options'),
                correct_answer=suggestion.question_data['correct_answer'],
                explanation=suggestion.question_data.get('explanation'),
                time_limit=suggestion.question_data.get('time_limit', 30)
            )
            db.add(new_question)

        db.commit()
        return {"status": "success"}
    finally:
        db.close()


# Для достижений
@router.get("/achievements/my")
async def get_my_achievements(
        user: UserOut = Depends(get_current_user)
):
    """Получить мои достижения"""
    return get_user_achievements(user.id)