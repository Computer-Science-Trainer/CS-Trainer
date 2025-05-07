import json
import os
from database import execute
from typing import Dict, Any, List, Optional


def get_current_questions() -> List[Dict[str, Any]]:
    rows = execute(
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer,"
        "sample_answer, terms_accepted, topic_code, proposer_id FROM current_questions"
    )
    return [
        {"id": r[0], "title": r[1],
         "question_text": r[2], "question_type": r[3], "difficulty": r[4],
         "options": json.loads(r[5]), "correct_answer": r[6], "sample_answer": r[7],
         "terms_accepted": bool(r[8]), "topic_code": r[9],
         "proposer_id": r[10]}
        for r in rows
    ]


def get_proposed_questions() -> List[Dict[str, Any]]:
    rows = execute(
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer,"
        "sample_answer, terms_accepted, topic_code, proposer_id FROM proposed_questions"
    )
    return [
        {"id": r[0], "title": r[1],
         "question_text": r[2], "question_type": r[3], "difficulty": r[4],
         "options": json.loads(r[5]), "correct_answer": r[6], "sample_answer": r[7],
         "terms_accepted": bool(r[8]), "topic_code": r[9], "proposer_id": r[10]}
        for r in rows
    ]


def add_question(q: Any) -> Dict[str, Any]:
    options_json = json.dumps(q.options)
    execute(
        "INSERT INTO current_questions (title, question_text, question_type, difficulty, options,"
        "correct_answer, sample_answer, terms_accepted, topic_code, proposer_id)"
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (q.title,
         q.question_text,
         q.question_type,
         q.difficulty,
         options_json,
         q.correct_answer,
         q.sample_answer,
         q.terms_accepted,
         q.topic_code,
         q.proposer_id)
    )
    row = execute(
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer, sample_answer,"
        "terms_accepted, topic_code, proposer_id FROM current_questions ORDER BY id DESC LIMIT 1",
        fetchone=True
    )
    return {
        "id": row[0], "title": row[1],
        "question_text": row[2], "question_type": row[3], "difficulty": row[4],
        "options": json.loads(row[5]), "correct_answer": row[6], "sample_answer": row[7],
        "terms_accepted": bool(row[8]), "topic_code": row[9], "proposer_id": row[10]
    }


def update_question(question_id: int, q: Any) -> Optional[Dict[str, Any]]:
    exists = execute(
        "SELECT id FROM current_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    if not exists:
        return None
    options_json = json.dumps(q.options)
    execute(
        "UPDATE current_questions SET title = %s, question_text = %s, question_type = %s, difficulty = %s,"
        "options = %s, correct_answer = %s, sample_answer = %s, terms_accepted = %s, topic_code = %s,"
        "proposer_id = %s WHERE id = %s",
        (q.title,
         q.question_text,
         q.question_type,
         q.difficulty,
         options_json,
         q.correct_answer,
         q.sample_answer,
         q.terms_accepted,
         q.topic_code,
         q.proposer_id,
         question_id)
    )
    row = execute(
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer, sample_answer,"
        "terms_accepted, topic_code, proposer_id FROM current_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    return {"id": row[0], "title": row[1],
            "question_text": row[2], "question_type": row[3], "difficulty": row[4],
            "options": json.loads(row[5]), "correct_answer": row[6], "sample_answer": row[7],
            "terms_accepted": bool(row[8]), "topic_code": row[9],
            "proposer_id": row[10]}


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
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer, sample_answer,"
        "terms_accepted, topic_code, proposer_id FROM proposed_questions WHERE id = %s",
        (question_id,),
        fetchone=True
    )
    if not row:
        return None
    (
        _, title, question_text, question_type, difficulty, options_json, correct_answer,
        sample_answer, terms_accepted, topic_code, proposer_id
    ) = row
    execute(
        "INSERT INTO current_questions (title, question_text, question_type, difficulty, options, correct_answer,"
        "sample_answer, terms_accepted, topic_code, proposer_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (title,
         question_text,
         question_type,
         difficulty,
         options_json,
         correct_answer,
         sample_answer,
         terms_accepted,
         topic_code,
         proposer_id)
    )
    execute(
        "DELETE FROM proposed_questions WHERE id = %s",
        (question_id,)
    )
    new = execute(
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer, sample_answer,"
        "terms_accepted, topic_code, proposer_id FROM current_questions ORDER BY id DESC LIMIT 1",
        fetchone=True
    )
    return {"id": new[0], "title": new[1],
            "question_text": new[2], "question_type": new[3], "difficulty": new[4],
            "options": json.loads(new[5]), "correct_answer": new[6], "sample_answer": new[7],
            "terms_accepted": bool(new[8]), "topic_code": new[9],
            "proposer_id": new[10]}


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
    options_json = json.dumps(q.options)
    execute(
        "INSERT INTO proposed_questions (title, question_text, question_type, difficulty, options, correct_answer,"
        "sample_answer, terms_accepted, topic_code, proposer_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (q.title,
         q.question_text,
         q.question_type,
         q.difficulty,
         options_json,
         q.correct_answer,
         q.sample_answer,
         q.terms_accepted,
         q.topic_code,
         q.proposer_id)
    )
    row = execute(
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer, sample_answer,"
        "terms_accepted, topic_code, proposer_id FROM proposed_questions ORDER BY id DESC LIMIT 1",
        fetchone=True
    )
    return {
        "id": row[0], "title": row[1],
        "question_text": row[2], "question_type": row[3], "difficulty": row[4],
        "options": json.loads(row[5]), "correct_answer": row[6], "sample_answer": row[7],
        "terms_accepted": bool(row[8]), "topic_code": row[9], "proposer_id": row[10]
    }


def update_proposed_question(
        question_id: int, q: Any) -> Optional[Dict[str, Any]]:
    exists = execute(
        "SELECT id FROM proposed_questions WHERE id = %s",
        (question_id,), fetchone=True
    )
    if not exists:
        return None
    options_json = json.dumps(q.options)
    execute(
        "UPDATE proposed_questions SET title=%s, question_text=%s, question_type=%s, difficulty=%s, options=%s,"
        "correct_answer=%s, sample_answer=%s, terms_accepted=%s, topic_code=%s, proposer_id=%s WHERE id=%s",
        (q.title, q.question_text, q.question_type, q.difficulty, options_json,
         q.correct_answer, q.sample_answer, q.terms_accepted, q.topic_code, q.proposer_id, question_id)
    )
    row = execute(
        "SELECT id, title, question_text, question_type, difficulty, options, correct_answer, sample_answer,"
        "terms_accepted, topic_code, proposer_id FROM proposed_questions WHERE id = %s",
        (question_id,), fetchone=True
    )
    return {
        "id": row[0], "title": row[1],
        "question_text": row[2], "question_type": row[3], "difficulty": row[4],
        "options": json.loads(row[5]), "correct_answer": row[6], "sample_answer": row[7],
        "terms_accepted": bool(row[8]), "topic_code": row[9], "proposer_id": row[10]
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
