import time
from database import execute

# CRUD operations for users

def save_user(email: str, password: str, username: str, verified: bool, verification_code: str) -> str:
    insert_user = """
        INSERT INTO users(email, password, username, achievement, avatar, verified, verification_code)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    execute(insert_user, (email, password, username, '0', '0', verified, verification_code))
    user = get_user_by_email(email)
    if not user:
        return 'Error: user not created'
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    execute(
        """
        INSERT INTO fundamentals(user_id, testsPassed, totalTests, lastActivity)
        VALUES (%s, %s, %s, %s)
        """,
        (user['id'], 0, 0, now)
    )
    execute(
        """
        INSERT INTO algorithms(user_id, testsPassed, totalTests, lastActivity)
        VALUES (%s, %s, %s, %s)
        """,
        (user['id'], 0, 0, now)
    )
    return 'success'


def change_db_users(email: str, *updates: tuple[str, any]) -> str:
    valid = ['password', 'username', 'achievement', 'avatar', 'verified', 'verification_code']
    for column, value in updates:
        if column not in valid:
            return f"Error: invalid column {column}"
        execute(f"UPDATE users SET {column} = %s WHERE email = %s", (value, email))
    return 'success'


def get_user_by_email(email: str) -> dict | None:
    row = execute(
        """
        SELECT id, email, password, username, achievement, avatar, verified, verification_code
        FROM users WHERE email = %s
        """,
        (email,), fetchone=True
    )
    if not row:
        return None
    keys = ['id','email','password','username','achievement','avatar','verified','verification_code']
    return dict(zip(keys, row))
