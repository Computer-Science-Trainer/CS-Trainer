import datetime
from fastapi import HTTPException
import random
from typing import List, Dict
from sqlalchemy.orm import Session
from database import SessionLocal
from models.db_models import Test, Question, UserAnswer, UserSuggestion, Topic, UserTestSession
from models.test_models import TestCreate, QuestionFilter, ExamConfig, TestUpdate
from sqlalchemy import func, Integer
from services.achievement_service import award_achievement, get_user_achievements
import logging
logger = logging.getLogger(__name__)


def create_test(test_data: TestCreate, user_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        for q in test_data.questions:
            if not db.query(Topic).filter(Topic.code == q.topic_code).first():
                raise HTTPException(400, detail=f"Topic {q.topic_code} not found")
        # Создаем тест
        db_test = Test(
            title=test_data.title,
            topics=test_data.topics,
            time_limit=test_data.time_limit,
            user_id=user_id,
            section=test_data.section
        )
        db.add(db_test)
        db.commit()

        # Создаем вопросы
        for q in test_data.questions:
            db_question = Question(
                title=q.title,
                question_text=q.question_text,
                question_type=q.question_type,
                difficulty=q.difficulty,
                options=q.options,
                correct_answer=q.correct_answer,
                topic_code=q.topic_code,
                terms_accepted=q.terms_accepted,
                proposer_id=user_id,
                test_id=db_test.id,
                created_at=datetime.utcnow()
            )
            db.add(db_question)

        db.commit()

        return {"test_id": db_test.id}
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def update_test(test_id: int, test_data: TestUpdate, user_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        db_test = db.query(Test).filter(Test.id == test_id).first()
        if not db_test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Обновляем только переданные поля
        if test_data.title is not None:
            db_test.title = test_data.title
        if test_data.topics is not None:
            db_test.topics = test_data.topics
        if test_data.time_limit is not None:
            db_test.time_limit = test_data.time_limit

        if test_data.questions is not None:
            # Удаляем старые вопросы
            db.query(Question).filter(Question.test_id == test_id).delete()

            # Добавляем новые вопросы
            for q in test_data.questions:
                db_question = Question(
                    title=q.title,
                    question_text=q.question_text,
                    question_type=q.question_type,
                    difficulty=q.difficulty,
                    options=q.options,
                    correct_answer=q.correct_answer,
                    sample_answer=q.sample_answer,
                    terms_accepted=q.terms_accepted,
                    topic_code=q.topic_code,
                    proposer_id=user_id,
                    test_id=db_test.id,
                    created_at=datetime.utcnow()
                )
                db.add(db_question)

        db.commit()
        return {"message": "Test updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def get_test(test_id: int, randomized: bool = False) -> List[Dict]:
    db: Session = SessionLocal()
    try:
        questions = db.query(Question).filter(Question.test_id == test_id).all()
        if not questions:
            return []

        result = []
        for q in questions:
            question_data = {
                "id": q.id,
                "title": q.title,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "options": q.options.copy() if q.options else [],
                "topic_code": q.topic_code
            }
            if not randomized:
                question_data.update({
                    "correct_answer": q.correct_answer,
                    "sample_answer": q.sample_answer
                })
            elif q.question_type == "single-choice":
                random.shuffle(question_data["options"])

            result.append(question_data)

        if randomized:
            random.shuffle(result)
            for q in result:
                q.pop("correct_answer", None)
                q.pop("sample_answer", None)

        return result
    finally:
        db.close()


def start_test_session(test_id: int, user_id: int) -> Dict:
    db = SessionLocal()
    try:
        # Проверяем существование теста
        test = db.query(Test).filter(Test.id == test_id).first()
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Создаем сессию тестирования
        session = UserTestSession(
            user_id=user_id,
            test_id=test_id,
            start_time=datetime.utcnow(),
            status="in_progress"
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        return {
            "session_id": session.id,
            "start_time": session.start_time,
            "time_limit": test.time_limit
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def submit_test_answers(test_id: int, user_id: int, answers: dict) -> Dict:
    db = SessionLocal()
    try:
        # Получаем активную сессию тестирования
        session = db.query(UserTestSession).filter(
            UserTestSession.user_id == user_id,
            UserTestSession.test_id == test_id,
            UserTestSession.status == "in_progress"
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")

        # Обновляем сессию
        session.end_time = datetime.utcnow()
        session.status = "completed"

        correct = 0
        for answer in answers.get("answers", []):
            question = db.query(Question).get(answer["question_id"])
            if not question:
                continue

            is_correct = False
            if question.question_type == "single-choice":
                is_correct = answer.get("answer") == question.correct_answer
            elif question.question_type == "open-ended":
                is_correct = answer.get("text", "").lower() == question.correct_answer.lower()

            if is_correct:
                correct += 1

            db.add(UserAnswer(
                user_id=user_id,
                question_id=question.id,
                given_answer=answer,
                is_correct=is_correct,
                response_time=answer.get("response_time", 0)
            ))

        score = int((correct / len(answers["answers"])) * 100) if answers["answers"] else 0
        session.score = score
        db.commit()

        return {
            "score": score,
            "correct": correct,
            "total": len(answers["answers"]),
            "time_spent": (session.end_time - session.start_time).total_seconds()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, detail=str(e))
    finally:
        db.close()


# Для вопросов, предложенных пользователями
def submit_question_suggestion(user_id: int, question_data: dict) -> dict:
    db = SessionLocal()
    try:
        suggestion = UserSuggestion(
            user_id=user_id,
            question_data={
                "title": question_data.get("title"),
                "question_text": question_data.get("question_text"),
                "question_type": question_data.get("question_type"),
                "options": question_data.get("options", []),
                "correct_answer": question_data.get("correct_answer"),
                "topic_code": question_data.get("topic_code")
            },
            status="pending",
            created_at=datetime.utcnow()
        )
        db.add(suggestion)
        db.commit()
        return {"status": "success", "suggestion_id": suggestion.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def update_suggestion_status(suggestion_id: int, new_status: str, comment: str = None):
    db = SessionLocal()
    try:
        suggestion = db.query(UserSuggestion).get(suggestion_id)
        if not suggestion:
            raise HTTPException(status_code=404, detail="Предложение не найдено")

        suggestion.status = new_status
        suggestion.admin_comment = comment

        if new_status == 'approved':
            # Проверяем, существует ли уже такой вопрос
            existing = db.query(Question).filter(
                Question.title == suggestion.question_data.get("title"),
                Question.question_text == suggestion.question_data.get("question_text")
            ).first()

            if not existing:
                new_question = Question(
                    title=suggestion.question_data.get("title"),
                    question_text=suggestion.question_data.get("question_text"),
                    question_type=suggestion.question_data.get("type"),
                    options=suggestion.question_data.get("options", []),
                    correct_answer=suggestion.question_data.get("correct_answer"),
                    topic_code=suggestion.question_data.get("topic_code"),
                    proposer_id=suggestion.user_id,
                    created_at=datetime.utcnow(),
                    terms_accepted=True
                )
                db.add(new_question)

        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def get_user_suggestions(user_id: int):
    db = SessionLocal()
    try:
        return db.query(UserSuggestion).filter(
            UserSuggestion.user_id == user_id
        ).order_by(UserSuggestion.created_at.desc()).all()
    finally:
        db.close()


def get_suggestions(status: str = None):
    db = SessionLocal()
    try:
        query = db.query(UserSuggestion)
        if status:
            query = query.filter(UserSuggestion.status == status)
        return query.order_by(UserSuggestion.id.desc()).all()
    finally:
        db.close()


def has_achievement(user_id: int, achievement_name: str, db: Session) -> bool:
    """Проверяет, есть ли у пользователя ачивка"""
    user_achievements = get_user_achievements(user_id)
    return any(ach['code'] == achievement_name for ach in user_achievements)


def grant_achievement(user_id: int, achievement_name: str, db: Session):
    """Выдает ачивку пользователю"""
    award_achievement(user_id, achievement_name)


def get_user_stats(user_id: int) -> Dict:
    db = SessionLocal()
    try:
        # Статистика по пройденным тестам
        test_stats = db.query(
            UserTestSession.test_id,
            func.count(UserTestSession.id).label("attempts"),
            func.max(UserTestSession.score).label("best_score"),
            func.avg(UserTestSession.score).label("average_score")
        ).filter(
            UserTestSession.user_id == user_id,
            UserTestSession.status == "completed"
        ).group_by(UserTestSession.test_id).all()

        # Общая статистика
        total_stats = db.query(
            func.count(UserAnswer.id).label("total_answers"),
            func.sum(func.cast(UserAnswer.is_correct, Integer)).label("correct_answers"),
            func.avg(UserAnswer.response_time).label("avg_response_time")
        ).filter(UserAnswer.user_id == user_id).first()

        return {
            "test_stats": [
                {
                    "test_id": stat.test_id,
                    "attempts": stat.attempts,
                    "best_score": stat.best_score,
                    "average_score": float(stat.average_score) if stat.average_score else 0
                } for stat in test_stats
            ],
            "total_stats": {
                "total_answers": total_stats.total_answers or 0,
                "correct_answers": total_stats.correct_answers or 0,
                "accuracy": (
                            total_stats.correct_answers / total_stats.total_answers * 100) if total_stats.total_answers else 0,
                "avg_response_time": float(total_stats.avg_response_time) if total_stats.avg_response_time else 0
            }
        }
    finally:
        db.close()


def get_questions_by_filter(user_id: int, filters: QuestionFilter) -> List[Dict]:
    db = SessionLocal()
    try:
        query = db.query(Question).join(Test, Question.test_id == Test.id)

        # Фильтрация по теме
        if filters.topics:
            query = query.filter(Test.topics.op('&&')(filters.topics))

        # Вопросы с ошибками
        if filters.include_wrong and user_id:
            wrong_answers = db.query(UserAnswer.question_id).filter(
                UserAnswer.user_id == user_id,
                UserAnswer.is_correct == False
            )
            query = query.filter(Question.id.in_(wrong_answers))

        questions = query.offset(filters.skip).limit(filters.limit).all()

        # Перемешивание
        random.shuffle(questions)
        result = []
        for q in questions:
            question_data = {
                "id": q.id,
                "question_text": q.text,
                "question_type": q.type,
                "options": q.options if q.options else None,
                "time_limit": q.time_limit,
                "topics": [q.topic_code]
            }
            if q.type == 'choice' and question_data['options']:
                random.shuffle(question_data['options'])
            result.append(question_data)

        return result
    finally:
        db.close()


def get_topic_stats(user_id: int) -> Dict[str, int]:
    db = SessionLocal()
    try:
        stats = db.execute("""
            SELECT q.topic_code, COUNT(*) as error_count
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.id
            WHERE ua.user_id = :user_id AND ua.is_correct = False
            GROUP BY q.topic_code
        """, {'user_id': user_id}).fetchall()

        return {row[0]: row[1] for row in stats}
    finally:
        db.close()


def get_questions_by_topic(topic_code: str, limit: int = 10) -> List[Dict]:
    db = SessionLocal()
    try:
        questions = db.query(Question).filter(
            Question.topic_code == topic_code
        ).limit(limit).all()

        return [{
            "id": q.id,
            "title": q.title,
            "question_text": q.question_text,
            "difficulty": q.difficulty
        } for q in questions]
    finally:
        db.close()


def generate_exam(user_id: int, config: ExamConfig) -> Dict:
    db = SessionLocal()
    try:
        questions = db.query(Question).join(Test).filter(
            Question.topic_code == config.topic  # Ищем вопросы из тестов с указанной темой
        ).order_by(func.random()).limit(config.question_count).all()

        if not questions:
            raise HTTPException(
                status_code=404,
                detail=f"No questions found for topic: {config.topic}"
            )

        # Создаем экзаменационную сессию
        session = UserTestSession(
            user_id=user_id,
            test_id=None,  # Для экзамена test_id не указан
            start_time=datetime.utcnow(),
            status="in_progress",
            time_limit=config.time_limit,
            exam_mode=True  # Добавляем флаг экзамена
        )
        db.add(session)
        db.commit()

        return {
            "session_id": session.id,
            "questions": [
                {
                    "id": q.id,
                    "question_text": q.question_text,
                    "question_type": q.type,
                    "options": q.options if q.options else None,
                    "time_limit": q.time_limit
                } for q in questions
            ],
            "time_limit": config.time_limit
        }
    finally:
        db.close()


def submit_exam_answers(session_id: int, user_id: int, answers: dict) -> Dict:
    db = SessionLocal()
    try:
        session = db.query(UserTestSession).get(session_id)
        if not session or session.user_id != user_id:
            raise HTTPException(status_code=404, detail="Сессия не найдена")

        # Проверка времени
        time_spent = (datetime.utcnow() - session.start_time).total_seconds()
        if session.time_limit and time_spent > session.time_limit:
            session.status = "time_expired"
            db.commit()
            raise HTTPException(status_code=400, detail="Время вышло")

        # Обработка каждого ответа
        correct = 0
        for answer in answers.get("answers", []):
            question = db.query(Question).get(answer["question_id"])
            if not question:
                continue

            # Проверка правильности
            is_correct = check_answer(question, answer["given_answer"])
            if is_correct:
                correct += 1

            # Сохранение ответа
            db.add(UserAnswer(
                user_id=user_id,
                question_id=question.id,
                given_answer=answer["given_answer"],
                is_correct=is_correct,
                response_time=answer.get("response_time", 0),
                test_session_id=session_id
            ))

        # Расчет результатов
        total = len(answers.get("answers", []))
        score = int((correct / total) * 100) if total > 0 else 0

        # Обновление сессии
        session.end_time = datetime.utcnow()
        session.status = "completed"
        session.score = score

        # Обновление статистики
        update_user_stats(user_id, score)

        db.commit()

        return {
            "score": score,
            "correct": correct,
            "total": total,
            "time_spent": time_spent
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def check_answer(question: Question, user_answer: dict) -> bool:
    """Проверка ответа с учетом структуры БД"""
    if question.question_type == "single-choice":
        return user_answer.get("answer") == question.correct_answer
    elif question.question_type == "open-ended":
        return user_answer.get("text", "").strip().lower() == question.correct_answer.strip().lower()
    return False

