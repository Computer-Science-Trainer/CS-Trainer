import time
from database import execute
import json
from security import hash_password


# CRUD operations for users
def save_user(email: str, password: str, username: str,
              verified: bool, verification_code: str) -> str:
    password = hash_password(password)
    insert_user = """
        INSERT INTO users(email, password, username, verified, verification_code)
        VALUES (%s, %s, %s, %s, %s)
    """
    execute(
        insert_user,
        (email,
         password,
         username,
         verified,
         verification_code))
    user = get_user_by_email(email)
    if not user:
        return 'Error: user not created'
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    execute(
        """
        INSERT INTO fundamentals(user_id, score, testsPassed, totalTests, lastActivity)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user['id'], 0, 0, 0, now)
    )
    execute(
        """
        INSERT INTO algorithms(user_id, score, testsPassed, totalTests, lastActivity)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user['id'], 0, 0, 0, now)
    )
    return 0


def change_db_users(email: str, *updates: tuple[str, any]) -> str:
    valid = [
        'password',
        'username',
        'email',
        'achievement',
        'avatar',
        'verified',
        'verification_code',
        'telegram',
        'github',
        'website',
        'bio',
        'refresh_token'
    ]
    for column, value in updates:
        if column not in valid:
            return f"Error: invalid column {column}"
        if column == 'password':
            value = hash_password(value)
        execute(
            f"UPDATE users SET {column} = %s WHERE email = %s", (value, email))
    return 'success'


def get_user_by_email(email: str) -> dict | None:
    row = execute(
        """
        SELECT id, email, password, username, achievement, avatar, verified, verification_code,
               telegram, github, website, bio
        FROM users WHERE email = %s
        """,
        (email,), fetchone=True
    )
    if not row:
        return None
    keys = [
        'id', 'email', 'password', 'username', 'achievement', 'avatar',
        'verified', 'verification_code', 'telegram', 'github', 'website', 'bio'
    ]
    return dict(zip(keys, row))


def get_user_by_username(username: str) -> dict | None:
    """
    Возвращает пользователя по username или None.
    """
    row = execute(
        """
        SELECT id, email, password, username, achievement, avatar, verified, verification_code,
               telegram, github, website, bio
        FROM users WHERE username = %s
        """,
        (username,), fetchone=True
    )
    if not row:
        return None
    keys = [
        'id', 'email', 'password', 'username', 'achievement', 'avatar',
        'verified', 'verification_code', 'telegram', 'github', 'website', 'bio'
    ]
    return dict(zip(keys, row))


def save_user_test(user_id: int, test_type: str, section: str,
                   passed: int, total: int, topics: list[int]) -> None:
    """Save a test session for a user with type and section"""
    average = passed / total if total else 0
    execute(
        """
        INSERT INTO tests(type, section, user_id, passed, total, average, earned_score, topics)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (test_type, section, user_id, passed,
         total, average, passed, json.dumps(topics))
    )


def get_user_tests(user_id: int) -> list[dict]:
    """Retrieve all test sessions for a user, including topic codes"""
    rows = execute(
        "SELECT id, type, section, passed, total, average, earned_score, topics, created_at"
        " FROM tests WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,)
    )
    result = []
    for test_id, test_type, sect, passed, total, average, earned_score, topics_json, created_at in rows:
        raw_ids = json.loads(topics_json)
        if isinstance(raw_ids, list):
            topic_ids = raw_ids
        elif raw_ids is None:
            topic_ids = []
        else:
            topic_ids = [raw_ids]
        if topic_ids:
            placeholders = ",".join(["%s"] * len(topic_ids))
            rows2 = execute(
                f"SELECT label FROM topics WHERE id IN ({placeholders})",
                tuple(topic_ids)
            )
            topic_codes = [str(r[0]) for r in rows2]
        else:
            topic_codes = []
        result.append({
            "id": test_id,
            "type": test_type,
            "section": sect,
            "passed": passed,
            "total": total,
            "average": average,
            "earned_score": earned_score,
            "topics": topic_codes,
            "created_at": created_at
        })
    return result


def get_user_scores(user_id: int) -> dict[str, int]:
    fund_row = execute(
        "SELECT score FROM fundamentals WHERE user_id = %s",
        (user_id,), fetchone=True
    )
    fund_score = fund_row[0] if fund_row and fund_row[0] is not None else 0
    alg_row = execute(
        "SELECT score FROM algorithms WHERE user_id = %s",
        (user_id,), fetchone=True
    )
    alg_score = alg_row[0] if alg_row and alg_row[0] is not None else 0
    return {"fundamentals": fund_score, "algorithms": alg_score}


def delete_user_by_id(user_id: int) -> bool:
    try:
        execute("DELETE FROM user_achievements WHERE user_id = %s", (user_id,))
        execute("DELETE FROM tests WHERE user_id = %s", (user_id,))
        execute("DELETE FROM fundamentals WHERE user_id = %s", (user_id,))
        execute("DELETE FROM algorithms WHERE user_id = %s", (user_id,))
        execute("DELETE FROM users WHERE id = %s", (user_id,))
        return True
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        return False


def set_refresh_token(user_id: int, refresh_token: str):
    execute("UPDATE users SET refresh_token = %s WHERE id = %s",
            (refresh_token, user_id))


def get_user_by_refresh_token(refresh_token: str) -> dict | None:
    row = execute(
        "SELECT id, email, password, username, achievement, avatar, "
        "verified, verification_code, telegram, github, website, bio "
        "FROM users WHERE refresh_token = %s",
        (refresh_token,), fetchone=True
    )
    if not row:
        return None
    keys = [
        'id', 'email', 'password', 'username', 'achievement', 'avatar',
        'verified', 'verification_code', 'telegram', 'github', 'website', 'bio'
    ]
    return dict(zip(keys, row))


def get_user_by_id(user_id: int) -> dict | None:
    """Return user dict by user id or None"""
    row = execute(
        """
        SELECT id, email, password, username, achievement, avatar, verified, verification_code,
               telegram, github, website, bio
        FROM users WHERE id = %s
        """,
        (user_id,), fetchone=True
    )
    if not row:
        return None
    keys = ['id', 'email', 'password', 'username', 'achievement', 'avatar',
            'verified', 'verification_code', 'telegram', 'github', 'website', 'bio']
    return dict(zip(keys, row))
