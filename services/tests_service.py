from fastapi import HTTPException
from database import execute
from services.user_service import save_user_test, get_user_scores
import datetime
import json
import random
import asyncio
from services.achievement_service import check_and_award


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
        raise HTTPException(
            status_code=400, detail={
                "code": "invalid_section"})
    save_user_test(user_id, "practice", db_section, 0, 0, topic_ids)
    row = execute(
        "SELECT id FROM tests WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
        (user_id,), fetchone=True
    )
    test_id = row[0]
    get_test_questions(user_id, test_id)
    return test_id


def get_test_questions(user_id: int, test_id: int) -> dict:
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
    if question_ids:
        placeholders = ",".join(["%s"] * len(question_ids))
        rows = execute(
            f"SELECT id, question_text, question_type, difficulty, options "
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
                    "question_text": r[1], "question_type": r[2], "difficulty": r[3],
                    "options": json.loads(r[4]) if r[4] else []
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
            f"SELECT id, question_text, question_type, difficulty, options "
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
                    f"SELECT id, question_text, question_type, difficulty, options "
                    f"FROM current_questions WHERE id NOT IN ({excl_ph}) "
                    "ORDER BY RAND() LIMIT %s",
                    tuple([q[0] for q in selected]) + (needed,)
                )
            else:
                more = execute(
                    "SELECT id, question_text, question_type, difficulty, options "
                    "FROM current_questions ORDER BY RAND() LIMIT %s",
                    (needed,)
                )
            rows = selected + list(more)
    else:
        rows = execute(
            "SELECT id, question_text, question_type, difficulty, options "
            "FROM current_questions ORDER BY RAND() LIMIT 10"
        )
    questions = []
    for q_id, text, qtype, diff, opts_json in rows:
        questions.append({
            "id": q_id,
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
    end_time = datetime.datetime.now(
        moscow_tz) + datetime.timedelta(minutes=total_minutes)
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
        return {"passed": passed, "total": total,
                "average": average, "earned_score": earned_score}
    submitted = {ans.question_id: ans.answer for ans in answers}
    if not submitted:
        raise HTTPException(
            status_code=400, detail={
                "code": "no_answers_provided"})
    placeholders = ",".join(["%s"] * len(submitted))
    rows = execute(
        f"SELECT id, correct_answer, difficulty, question_type "
        f"FROM current_questions WHERE id IN ({placeholders})",
        tuple(submitted.keys())
    )
    qtype_map = {r[0]: r[3] for r in rows}
    for qid, ans_list in submitted.items():
        qtype = qtype_map.get(qid)
        if qtype == 'open-ended':
            if len(ans_list) != 1 or len(ans_list[0] or '') > 128:
                raise HTTPException(
                    status_code=400, detail={
                        "code": "answer_too_long"})
        elif len(ans_list) > 8:
            raise HTTPException(
                status_code=400, detail={
                    "code": "too_many_answers"})
        else:
            if any(len(item) > 256 for item in ans_list):
                raise HTTPException(
                    status_code=400, detail={"code": "answer_item_too_long"})
    passed = 0
    weighted_score = 0
    weight_map = {"easy": 1, "medium": 2, "hard": 5}
    correct_answers = []
    user_answers_list = []
    for i, (qid, correct_json, difficulty, question_type) in enumerate(rows):
        correct_val = json.loads(correct_json)
        user_ans = submitted[qid]
        if question_type == 'multiple-choice' and len(correct_val) > 1:
            norm_c = sorted(str(c).strip().lower() for c in correct_val)
            norm_u = sorted(str(a).strip().lower() for a in user_ans)
            is_correct = norm_c == norm_u
        else:
            is_correct = len(user_ans) == len(correct_val) and all(
                str(c).strip().lower() == str(a).strip().lower()
                for c, a in zip(correct_val, user_ans)
            )
        if is_correct:
            passed += 1
            weighted_score += weight_map.get(difficulty, 0)

        correct_answers.append({
            "question_id": qid,
            "correct_answer": correct_val
        })
        user_answers_list.append({
            "question_id": qid,
            "user_answer": submitted[qid],
            "is_correct": is_correct
        })
    total = len(answers)
    average = passed / total if total else 0.0
    execute(
        "UPDATE tests SET passed = %s, total = %s, average = %s, earned_score = %s WHERE id = %s",
        (passed, total, average, weighted_score, test_id)
    )
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
    for ans in user_answers_list:
        usr_json = json.dumps(ans["user_answer"], ensure_ascii=False)
        corr_val = next(c["correct_answer"]
                        for c in correct_answers if c["question_id"] == ans["question_id"])
        corr_json = json.dumps(corr_val, ensure_ascii=False)
        execute(
            "INSERT INTO test_answers (test_id, question_id, user_answer, correct_answer, is_correct) "
            "VALUES (%s, %s, %s, %s, %s)",
            (test_id, ans["question_id"], usr_json,
             corr_json, ans["is_correct"])
        )
    try:
        scores = get_user_scores(user_id)
        total_score = scores.get('fundamentals', 0) + \
            scores.get('algorithms', 0)
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        if loop and loop.is_running():
            loop.create_task(
                asyncio.to_thread(
                    check_and_award,
                    user_id,
                    tests_passed=total_score))
        else:
            import threading
            threading.Thread(target=check_and_award, args=(user_id,), kwargs={
                             "tests_passed": total_score}, daemon=True).start()
    except Exception:
        pass
    return {
        "passed": passed,
        "total": total,
        "average": average,
        "earned_score": weighted_score,
        "correct_answers": correct_answers,
        "user_answers": user_answers_list
    }


# Add retrieval of stored answers for a test
def get_test_answers(user_id: int, test_id: int) -> dict:
    row = execute(
        "SELECT user_id FROM tests WHERE id = %s",
        (test_id,), fetchone=True
    )
    if not row:
        raise HTTPException(status_code=404, detail={"code": "test_not_found"})
    if row[0] != user_id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    rows = execute(
        "SELECT ta.question_id, ta.correct_answer, ta.user_answer, ta.is_correct, cq.question_type, cq.difficulty "
        "FROM test_answers ta "
        "JOIN current_questions cq ON ta.question_id = cq.id "
        "WHERE ta.test_id = %s ORDER BY ta.id",
        (test_id,)
    )
    weight_map = {"easy": 1, "medium": 2, "hard": 5}
    answer_list = []
    for qid, corr, ua, ic, qtype, diff in rows:
        is_correct = bool(ic)
        answer_list.append({
            "question_id": qid,
            "question_type": qtype,
            "difficulty": diff,
            "user_answer": json.loads(ua),
            "correct_answer": json.loads(corr),
            "is_correct": is_correct,
            "points_awarded": weight_map.get(diff, 0) if is_correct else 0
        })
    return {"answers": answer_list}
