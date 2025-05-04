from datetime import datetime
from fastapi import HTTPException
import random
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from local_db import SessionLocal
from models.db_models import Test, Question, UserAnswer, UserTestSession, UserSuggestion, Achievement, AchievementTemplate
from models.test_models import TestCreate, QuestionCreate, UserAnswerSubmit, TestSubmit, QuestionFilter, ExamConfig
from sqlalchemy import func, Integer
import logging
logger = logging.getLogger(__name__)


def create_test(test_data: TestCreate, user_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        # Создаем тест
        db_test = Test(
            title=test_data.title,
            topics=test_data.topics,
            time_limit=test_data.time_limit,
        )
        db.add(db_test)
        db.commit()
        db.refresh(db_test)

        # Создаем вопросы
        for q in test_data.questions:
            db_question = Question(
                test_id=db_test.id,
                text=q.text,
                type=q.type,
                options=q.options,
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                time_limit=q.time_limit,
            )
            db.add(db_question)

        db.commit()

        # # Создаем первоначальную версию теста
        # create_test_version(db_test.id, user_id)

        return {"test_id": db_test.id}
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def update_test(test_id: int, test_data: TestCreate, user_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        # Получаем тест
        db_test = db.query(Test).filter(Test.id == test_id).first()
        if not db_test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Обновляем данные теста
        db_test.title = test_data.title
        db_test.topics = test_data.topics
        db_test.time_limit = test_data.time_limit

        # Удаляем старые вопросы
        db.query(Question).filter(Question.test_id == test_id).delete()

        # Добавляем новые вопросы
        for q in test_data.questions:
            db_question = Question(
                test_id=db_test.id,
                text=q.text,
                type=q.type,
                options=q.options,
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                time_limit=q.time_limit
            )
            db.add(db_question)

        db.commit()

        # Создаем новую версию теста
        create_test_version(test_id, user_id)

        return {"message": "Test updated successfully"}
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_test(test_id: int, randomized: bool = False) -> List[Dict]:
    db: Session = SessionLocal()
    try:
        questions = db.query(Question).filter(Question.test_id == test_id).all()

        result = []
        for q in questions:
            question_data = {
                "id": q.id,
                "test_id": q.test_id,
                "text": q.text,
                "type": q.type,
                "options": q.options.copy() if q.options else None,  # Создаем копию списка
                "time_limit": q.time_limit
            }

            # Для клиента не отправляем правильные ответы
            if not randomized:
                question_data["correct_answer"] = q.correct_answer
                question_data["explanation"] = q.explanation

            result.append(question_data)

        if randomized:
            random.shuffle(result)
            for q in result:
                if q['type'] == 'choice' and q['options']:
                    random.shuffle(q['options'])
                elif q['type'] == 'order' and q['options']:
                    # Сохраняем правильный порядок во временном поле
                    q['_correct_order'] = q['options'].copy()
                    random.shuffle(q['options'])  # Перемешиваем для показа

                    # Удаляем служебные данные в randomized-режиме
                q.pop('correct_answer', None)
                q.pop('explanation', None)

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

        # Сохраняем ответы и считаем правильные
        correct_answers = 0
        total_questions = 0

        answers_list = answers.get("answers", [])

        for answer in answers_list:
            question_id = answer.get("question_id")
            given_answer = answer.get("given_answer", {})
            response_time = answer.get("response_time", 0.0)

            question = db.query(Question).filter(Question.id == question_id,
                                                 Question.test_id == test_id).first()
            if not question:
                raise HTTPException(400, f"Question {answer['question_id']} not found in test {test_id}")

            total_questions += 1
            is_correct = False

            # Проверяем правильность ответа в зависимости от типа вопроса
            if question.type == 'choice':
                is_correct = set(given_answer.get('answers', [])) == set(
                    question.correct_answer.get('answers', []))
            elif question.type == 'open':
                is_correct = given_answer.get('text', '').lower() == question.correct_answer.get('text', '').lower()

            elif question.type == 'order':
                is_correct = given_answer.get('order', []) == question.correct_answer.get('order', [])

            if is_correct:
                correct_answers += 1

            # Сохраняем ответ пользователя
            user_answer = UserAnswer(
                user_id=user_id,
                question_id=question_id,
                given_answer=given_answer,
                is_correct=is_correct,
                response_time=response_time,
                # test_session_id=session.id
            )
            db.add(user_answer)

        # Рассчитываем результат
        score = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0

        session.score = score
        check_achievements(user_id, db)
        db.commit()
        return {
            "score": score,
            "correct_answers": correct_answers,
            "total_questions": total_questions,
            "time_spent": (session.end_time - session.start_time).total_seconds()
        }
    finally:
        db.close()


# Для вопросов, предложенных пользователями
def submit_question_suggestion(user_id: int, question_data: dict) -> dict:
    db = SessionLocal()
    try:
        sfull_data = {
            "question": suggestion_data,
            "meta": {
                "created_at": datetime.utcnow().isoformat(),
                "admin_comment": None,
                "status": "pending"
            }
        }

        suggestion = UserSuggestion(
            user_id=user_id,
            question_data=full_data,  # Все храним в JSON
            status="pending"  # Дублируем статус для простоты фильтрации
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

        # Обновляем данные в JSON
        question_data = suggestion.question_data
        question_data["meta"]["status"] = new_status
        question_data["meta"]["admin_comment"] = comment

        # Обновляем и основное поле status для фильтрации
        suggestion.status = new_status
        suggestion.question_data = question_data
        if update.status == 'approved':
            check_contribution_achievements(suggestion.user_id, db)
            check_achievements(suggestion.user_id, db)

        db.commit()
        return {"status": "success"}
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


# Для достижений
def check_achievements(user_id: int, db: Session):
    """Проверяет и выдает ачивки пользователю"""
    # Проверяем существование пользователя
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        logger.warning(f"User {user_id} not found when checking achievements")
        return
    # stats = get_user_stats(user_id)

    test_sessions = db.query(UserTestSession).filter_by(
        user_id=user_id,
        status="completed"
    ).all()

    achievements_to_grant = []

    # 1. Первый тест
    if len(test_sessions) == 1 and not has_achievement(user_id, "first_test_passed", db):
        achievements_to_grant.append("first_test_passed")

    # 2. Идеальный результат
    perfect_sessions = [s for s in test_sessions if s.score == 100]
    if perfect_sessions and not has_achievement(user_id, "perfect_score", db):
        achievements_to_grant.append("perfect_score")

    # 3. Быстрое прохождение
    fast_sessions = [
        s for s in test_sessions
        if (s.end_time - s.start_time).total_seconds() < 300  # 5 минут
    ]
    if fast_sessions and not has_achievement(user_id, "fast_learner", db):
        achievements_to_grant.append("fast_learner")

    # 4. Марафонец
    if len(test_sessions) >= 10 and not has_achievement(user_id, "marathoner", db):
        achievements_to_grant.append("marathoner")

    # Выдаем все новые достижения одним запросом
    for achievement_name in achievements_to_grant:
        grant_achievement(user_id, achievement_name, db)


def grant_achievement(user_id: int, achievement_name: str, db: Session):
    """Выдает ачивку пользователю"""
    try:
        template = db.query(AchievementTemplate).filter_by(name=achievement_name).first()
        if not template:
            logger.error(f"Achievement template {achievement_name} not found!")
            return

        # Проверяем, нет ли уже такого достижения
        existing = db.query(Achievement).filter_by(
            user_id=user_id,
            name=achievement_name
        ).first()

        if existing:
            return

        achievement = Achievement(
            user_id=user_id,
            name=template.name,
            title=template.title,
            description=template.description,
            icon=template.icon,
            unlocked_at=datetime.utcnow()
        )
        db.add(achievement)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error granting achievement {achievement_name} to user {user_id}: {str(e)}")
        raise


def has_achievement(user_id: int, achievement_name: str, db: Session) -> bool:
    """Проверяет, есть ли у пользователя ачивка"""
    return db.query(Achievement).filter_by(
        user_id=user_id,
        name=achievement_name
    ).first() is not None


def check_contribution_achievements(user_id: int):
    """Проверяет достижения, связанные с вкладом пользователя"""
    # db = SessionLocal()
    try:
        count = db.query(UserSuggestion).filter(
            UserSuggestion.user_id == user_id,
            UserSuggestion.status == 'approved'
        ).count()

        achievements = []
        if count >= 1 and not has_achievement(user_id, 'first_contribution', db):
            template = db.query(AchievementTemplate).filter_by(name='first_contribution').first()
            if template:
                achievements.append(Achievement(
                    user_id=user_id,
                    name=template.name,
                    title=template.title,
                    description=template.description,
                    icon=template.icon,
                    unlocked_at=datetime.utcnow()
                ))

        for ach in achievements:
            db.add(ach)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error checking contribution achievements for user {user_id}: {str(e)}")
        raise
    finally:
        db.close()


def get_user_achievements(user_id: int) -> List[Dict]:
    db = SessionLocal()
    try:
        return [
            {
                "name": a.name,
                "title": a.title,
                "description": a.description,
                "icon": a.icon,
                "unlocked_at": a.unlocked_at
            }
            for a in db.query(Achievement).filter_by(user_id=user_id).all()
        ]
    finally:
        db.close()


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


def get_questions_by_filter(user_id: int, filters: QuestionFilter, skip: int, limit: int) -> List[Dict]:
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

        questions = query.offset(skip).limit(limit).all()

        # Перемешивание
        random.shuffle(questions)
        result = []
        for q in questions:
            question_data = {
                "id": q.id,
                "text": q.text,
                "type": q.type,
                "options": q.options if q.options else None,
                "time_limit": q.time_limit,
                # Темы берем из родительского теста
                "topics": db.query(Test.topics).filter(Test.id == q.test_id).scalar()
            }
            if q.type == 'choice' and question_data['options']:
                random.shuffle(question_data['options'])
            result.append(question_data)

        return result
    finally:
        db.close()


def get_topic_stats(user_id: int):
    db = SessionLocal()
    try:
        # Анализируем ошибки по темам
        topic_errors = db.execute("""
            SELECT jsonb_array_elements_text(t.topics) as topic,
                   COUNT(*) as error_count
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.id
            JOIN tests t ON q.test_id = t.id
            WHERE ua.user_id = :user_id AND ua.is_correct = False
            GROUP BY topic
            ORDER BY error_count DESC
        """, {'user_id': user_id}).fetchall()

        return [{"topic": row[0], "error_count": row[1]} for row in topic_errors]
    finally:
        db.close()


def get_wrong_answers(user_id: int, limit: int = 5) -> List:
    db = SessionLocal()
    try:
        # Получаем вопросы с ошибками
        wrong_answers = db.query(
            UserAnswer.question_id,
            func.count(UserAnswer.id).label('error_count')
        ).filter(
            UserAnswer.user_id == user_id,
            UserAnswer.is_correct == False
        ).group_by(UserAnswer.question_id).all()

        # Получаем похожие вопросы
        similar_questions = []
        for q_id in wrong_answers:
            original = db.query(Question).filter(Question.id == q_id).first()
            if original:
                similar = db.query(Question).filter(
                    Question.test_id == original.test_id,
                    Question.id != q_id
                ).limit(2).all()
                similar_questions.extend(similar)

        return [{
            "id": q.id,
            "text": q.text,
            "type": q.type,
            "options": q.options if q.options else None
        } for q in similar_questions]
    finally:
        db.close()


def get_similar_questions(question_id: int, user_id: int, limit: int = 5) -> List[Dict]:
    """Получение похожих вопросов на тот, где была ошибка"""
    db = SessionLocal()
    try:
        # Получаем тему исходного вопроса
        original = db.query(Question).filter(Question.id == question_id).first()
        if not original:
            return []

        # Ищем вопросы из того же теста
        similar = db.query(Question).filter(
            Question.test_id == original.test_id,
            Question.id != question_id
        ).limit(limit).all()

        return [{
            "id": q.id,
            "text": q.text,
            "type": q.type,
            "options": random.sample(q.options, len(q.options)) if q.options else None
        } for q in similar]
    finally:
        db.close()


def generate_exam(user_id: int, config: ExamConfig) -> Dict:
    db = SessionLocal()
    try:
        questions = db.query(Question).join(Test).filter(
            Test.topics.contains([config.topic])  # Ищем вопросы из тестов с указанной темой
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
                    "text": q.text,
                    "type": q.type,
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
    """Проверка ответа в зависимости от типа вопроса"""
    if question.type == 'choice':
        return set(user_answer.get('answers', [])) == set(question.correct_answer.get('answers', []))
    elif question.type == 'open':
        return user_answer.get('text', '').lower() == question.correct_answer.get('text', '').lower()
    elif question.type == 'order':
        return user_answer.get('order', []) == question.correct_answer.get('order', [])
    return False
