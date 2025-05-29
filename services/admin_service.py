import json
import os
from database import execute
from typing import Dict, Any, List, Optional
from services.validation_service import (
    validate_question_text,
    validate_option_list
)


def validate_question_data(q: Any):
    # centralize validation
    validate_question_text(q.question_text)
    validate_option_list(q.question_type, q.options, code_prefix='option')
    validate_option_list(
        q.question_type,
        q.correct_answer,
        code_prefix='correct_answer')


def get_current_questions() -> List[Dict[str, Any]]:
    rows = execute(
        "SELECT id, question_text, question_type, difficulty, options, "
        "correct_answer, topic_code, proposer_id FROM current_questions"
    )
    result = []
    for r in rows:
        opts = json.loads(r[4])
        corr = json.loads(r[5])
        if isinstance(corr, str):
            corr = json.loads(corr)
        result.append({
            "id": r[0],
            "question_text": r[1], "question_type": r[2], "difficulty": r[3],
            "options": opts, "correct_answer": corr,
            "topic_code": r[6], "proposer_id": r[7]
        })
    return result


def get_proposed_questions() -> List[Dict[str, Any]]:
    rows = execute(
        "SELECT id, question_text, question_type, difficulty, options, correct_answer, "
        "topic_code, proposer_id FROM proposed_questions"
    )
    result = []
    for r in rows:
        opts = json.loads(r[4])
        corr = json.loads(r[5])
        if isinstance(corr, str):
            corr = json.loads(corr)
        result.append({
            "id": r[0],
            "question_text": r[1], "question_type": r[2], "difficulty": r[3],
            "options": opts, "correct_answer": corr,
            "topic_code": r[6], "proposer_id": r[7]
        })
    return result


def add_question(q: Any) -> Dict[str, Any]:
    validate_question_data(q)
    options_json = json.dumps(q.options, ensure_ascii=False)
    correct_answer_json = json.dumps(q.correct_answer, ensure_ascii=False)
    execute(
        "INSERT INTO current_questions (question_text, question_type, difficulty, "
        "options, correct_answer, topic_code, proposer_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (q.question_text,
         q.question_type,
         q.difficulty,
         options_json,
         correct_answer_json,
         q.topic_code,
         q.proposer_id)
    )
    row = execute(
        "SELECT id, question_text, question_type, difficulty, options, correct_answer, topic_code, proposer_id "
        "FROM current_questions ORDER BY id DESC LIMIT 1",
        fetchone=True
    )
    return {
        "id": row[0],
        "question_text": row[1], "question_type": row[2], "difficulty": row[3],
        "options": json.loads(row[4]), "correct_answer": json.loads(row[5]),
        "topic_code": row[6], "proposer_id": row[7]
    }


def update_question(question_id: int, q: Any) -> Optional[Dict[str, Any]]:
    exists = execute(
        "SELECT id FROM current_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    if not exists:
        return None
    validate_question_data(q)
    options_json = json.dumps(q.options, ensure_ascii=False)
    correct_answer_json = json.dumps(q.correct_answer, ensure_ascii=False)
    execute(
        "UPDATE current_questions SET question_text = %s, question_type = %s, difficulty = %s, "
        "options = %s, correct_answer = %s, topic_code = %s, proposer_id = %s WHERE id = %s",
        (q.question_text,
         q.question_type,
         q.difficulty,
         options_json,
         correct_answer_json,
         q.topic_code,
         q.proposer_id,
         question_id)
    )
    row = execute(
        "SELECT id, question_text, question_type, difficulty, options, correct_answer, topic_code, proposer_id "
        "FROM current_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    return {"id": row[0],
            "question_text": row[1], "question_type": row[2], "difficulty": row[3],
            "options": json.loads(row[4]), "correct_answer": json.loads(row[5]),
            "topic_code": row[6], "proposer_id": row[7]}


def delete_question(question_id: int) -> bool:
    exists = execute(
        "SELECT id FROM current_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    if not exists:
        return False
    execute(
        "DELETE FROM current_questions WHERE id = %s",
        (question_id,)
    )
    return True


def approve_proposed_question(question_id: int) -> Optional[Dict[str, Any]]:
    row = execute(
        "SELECT id, question_text, question_type, difficulty, options, correct_answer, topic_code, proposer_id "
        "FROM proposed_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    if not row:
        return None
    (
        _, question_text, question_type, difficulty, options_json, correct_answer,
        topic_code, proposer_id
    ) = row
    execute(
        "INSERT INTO current_questions (question_text, question_type, difficulty, options, correct_answer, "
        "topic_code, proposer_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (question_text,
         question_type,
         difficulty,
         options_json,
         correct_answer,
         topic_code,
         proposer_id)
    )
    execute(
        "DELETE FROM proposed_questions WHERE id = %s",
        (question_id,)
    )
    new = execute(
        "SELECT id, question_text, question_type, difficulty, options, correct_answer, topic_code, proposer_id "
        "FROM current_questions ORDER BY id DESC LIMIT 1",
        fetchone=True
    )
    return {"id": new[0],
            "question_text": new[1], "question_type": new[2], "difficulty": new[3],
            "options": json.loads(new[4]), "correct_answer": json.loads(new[5]),
            "topic_code": new[6], "proposer_id": new[7]}


def reject_proposed_question(question_id: int) -> bool:
    exists = execute(
        "SELECT id FROM proposed_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    if not exists:
        return False
    execute(
        "DELETE FROM proposed_questions WHERE id = %s",
        (question_id,)
    )
    return True


def add_proposed_question(q: Any) -> Dict[str, Any]:
    validate_question_data(q)
    options_json = json.dumps(q.options, ensure_ascii=False)
    correct_answer_json = json.dumps(q.correct_answer, ensure_ascii=False)
    execute(
        "INSERT INTO proposed_questions (question_text, question_type, difficulty, options, "
        "correct_answer, topic_code, proposer_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (q.question_text,
         q.question_type,
         q.difficulty,
         options_json,
         correct_answer_json,
         q.topic_code,
         q.proposer_id)
    )
    row = execute(
        "SELECT id, question_text, question_type, difficulty, options, correct_answer, topic_code, proposer_id "
        "FROM proposed_questions ORDER BY id DESC LIMIT 1",
        fetchone=True
    )
    return {
        "id": row[0],
        "question_text": row[1], "question_type": row[2], "difficulty": row[3],
        "options": json.loads(row[4]), "correct_answer": json.loads(row[5]),
        "topic_code": row[6], "proposer_id": row[7]
    }


def update_proposed_question(
        question_id: int, q: Any) -> Optional[Dict[str, Any]]:
    exists = execute(
        "SELECT id FROM proposed_questions WHERE id = %s",
        (question_id,), fetchone=True
    )
    if not exists:
        return None
    validate_question_data(q)
    options_json = json.dumps(q.options, ensure_ascii=False)
    correct_answer_json = json.dumps(q.correct_answer, ensure_ascii=False)
    execute(
        "UPDATE proposed_questions SET question_text=%s, question_type=%s, difficulty=%s, options=%s, "
        "correct_answer=%s, topic_code=%s, proposer_id=%s WHERE id=%s",
        (q.question_text, q.question_type, q.difficulty, options_json,
         correct_answer_json, q.topic_code, q.proposer_id, question_id)
    )
    row = execute(
        "SELECT id, question_text, question_type, difficulty, options, correct_answer, topic_code, proposer_id "
        "FROM proposed_questions WHERE id = %s",
        (question_id,), fetchone=True
    )
    return {
        "id": row[0],
        "question_text": row[1], "question_type": row[2], "difficulty": row[3],
        "options": json.loads(row[4]), "correct_answer": json.loads(row[5]),
        "topic_code": row[6], "proposer_id": row[7]
    }


def is_user_admin(user_id: int) -> bool:
    """Return True if user_id is present in admins table"""
    return execute(
        "SELECT 1 FROM admins WHERE user_id = %s",
        (user_id,), fetchone=True
    ) is not None


def get_settings() -> Dict[str, Any]:
    return {
        "frontend_url": os.getenv("FRONTEND_URL") or "http://localhost:3000",
        "smtp_host": os.getenv("SMTP_HOST") or "localhost",
        "smtp_port": int(os.getenv("SMTP_PORT", 465)),
        "from_email": os.getenv("FROM_EMAIL") or "undefined",
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID") or "undefined",
        "github_client_id": os.getenv("GITHUB_CLIENT_ID") or "undefined"
    }
