from fastapi import HTTPException
from database import execute
from services.user_service import save_user_test
import datetime
import json
import random


def start_test(user_id: int, section: str, labels: list[str]) -> int:
    if labels:
        placeholders = ",".join(["%s"] * len(labels))
        rows = execute(
            f"SELECT id FROM topics WHERE label IN ({placeholders})",
            tuple(labels))
        topic_ids = [r[0] for r in rows]
    else:
        topic_ids = []
    section_map = {"FI": "fundamentals", "AS": "algorithms"}
    db_section = section_map.get(section)
    if not db_section:
        raise HTTPException(status_code=400, detail={"code": "invalid_section"})
    save_user_test(user_id, "practice", db_section, 0, 0, topic_ids)
    row = execute(
        "SELECT id FROM tests WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
        (user_id,), fetchone=True
    )
    test_id = row[0]
    get_test_questions(user_id, test_id)
    return test_id


def get_test_questions(user_id: int, test_id: int) -> dict:
    # fetch test topics and existing questions
    row = execute(
        "SELECT topics, questions, created_at FROM tests WHERE id = %s AND user_id = %s",
        (test_id, user_id), fetchone=True
    )
    if not row:
        raise HTTPException(status_code=404, detail={"code": "test_not_found"})
    topic_ids = json.loads(row[0]) or []
    questions_json = row[1]
    created_at = row[2]
    question_ids = json.loads(questions_json) if questions_json else []
    # if questions exist, load them
    if question_ids:
        placeholders = ",".join(["%s"] * len(question_ids))
        rows = execute(
            f"SELECT id, title, question_text, question_type, difficulty, options "
            f"FROM current_questions WHERE id IN ({placeholders})",
            tuple(question_ids)
        )
        id_to_row = {r[0]: r for r in rows}
        questions = []
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
        topics = []
        if topic_ids:
            placeholders = ",".join(["%s"] * len(topic_ids))
            topic_labels_rows = execute(
                f"SELECT label FROM topics WHERE id IN ({placeholders})",
                tuple(topic_ids)
            )
            topics = [r[0] for r in topic_labels_rows]
        # load test metadata
        end_time_row = execute(
            "SELECT end_time, passed, total, average, earned_score, section, created_at "
            "FROM tests WHERE id = %s",
            (test_id,), fetchone=True
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
    # select exactly 10 questions
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
    moscow_tz = datetime.timezone(datetime.timedelta(hours=3))
    end_time = datetime.datetime.now(moscow_tz) + datetime.timedelta(minutes=total_minutes)
    # record questions and end_time into DB
    question_ids = [q["id"] for q in questions]
    execute(
        "UPDATE tests SET questions = %s WHERE id = %s",
        (json.dumps(question_ids), test_id)
    )
    execute(
        "UPDATE tests SET end_time = %s WHERE id = %s",
        (end_time, test_id)
    )
    test_row = execute(
        "SELECT passed, total, average, earned_score, section, created_at, topics FROM tests WHERE id = %s",
        (test_id,), fetchone=True)
    if test_row:
        passed, total, average, earned_score, section, created_at_db, topics_json = test_row
    else:
        passed = total = average = earned_score = 0
        section = ""
        created_at_db = created_at
        topics_json = None
    if topics_json:
        topic_ids_db = json.loads(topics_json) or []
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


def submit_test(user_id: int, test_id: int, answers: list[dict]) -> dict:
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
            (test_id,), fetchone=True)
        if test_row:
            passed, total, average, earned_score = test_row
        else:
            passed = total = average = earned_score = 0
        return {"passed": passed, "total": total, "average": average, "earned_score": earned_score}
    submitted = {ans.question_id: ans.answer for ans in answers}
    q_ids = list(submitted.keys())
    if not q_ids:
        raise HTTPException(status_code=400, detail={"code": "no_answers_provided"})
    placeholders = ",".join(["%s"] * len(q_ids))
    rows = execute(
        f"SELECT id, correct_answer, difficulty FROM current_questions WHERE id IN ({placeholders})",
        tuple(q_ids)
    )
    passed = 0
    weighted_score = 0
    weight_map = {"easy": 1, "medium": 2, "hard": 5}
    for qid, correct, difficulty in rows:
        correct_str = str(correct).strip() if correct is not None else ''
        user_ans_str = str(submitted.get(qid, '')).strip()
        if correct_str and user_ans_str and user_ans_str == correct_str:
            passed += 1
            weighted_score += weight_map.get(difficulty, 0)
    total = len(answers)
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
    return {"passed": passed, "total": total, "average": average, "earned_score": weighted_score}
