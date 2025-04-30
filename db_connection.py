import pymysql
import json
import time
from dbutils.pooled_db import PooledDB
import redis


with open('database_user.json') as file:
    file_json_data = json.load(file)

pool = PooledDB(
    creator=pymysql,
    host=file_json_data['host'],
    user=file_json_data['user'],
    password=file_json_data['password'],
    database=file_json_data['database'],
    autocommit=True,
    mincached=5,
    maxcached=20,
)

redis_client = redis.Redis()


def _execute(query, params=None, fetchone=False):
    conn = pool.connection()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    result = cursor.fetchone() if fetchone else cursor.fetchall()
    cursor.close()
    conn.close()
    return result


def get_leaderboard(number_of_users=10):
    cache_key = f"leaderboard:{number_of_users}"

    fund_query = """
        SELECT f.id, f.user_id, f.score, f.testsPassed, f.totalTests, f.lastActivity,
               u.username, u.achievement, u.avatar
        FROM fundamentals AS f
        JOIN users AS u ON f.user_id = u.id
        ORDER BY f.score DESC
        LIMIT %s
    """
    alg_query = """
        SELECT a.id, a.user_id, a.score, a.testsPassed, a.totalTests, a.lastActivity,
               u.username, u.achievement, u.avatar
        FROM algorithms AS a
        JOIN users AS u ON a.user_id = u.id
        ORDER BY a.score DESC
        LIMIT %s
    """

    fundamentals_data = _execute(fund_query, (number_of_users,))
    algorithms_data = _execute(alg_query, (number_of_users,))
    fundamentals = [
        {
            'id': row[0],
            'user_id': row[1],
            'score': row[2],
            'testsPassed': row[3],
            'totalTests': row[4],
            'lastActivity': row[5],
            'username': row[6],
        }
        for row in fundamentals_data
    ]
    algorithms = [
        {
            'id': row[0],
            'user_id': row[1],
            'score': row[2],
            'testsPassed': row[3],
            'totalTests': row[4],
            'lastActivity': row[5],
            'username': row[6],
        }
        for row in algorithms_data
    ]
    result = {
        'fundamentals': fundamentals,
        'algorithms': algorithms
    }
    redis_client.setex(cache_key, 60, json.dumps(result, default=str))
    return result


def save_user(email, password, username, verified, verification_code):
    user_query = """
        INSERT INTO users(email, password, username, achievement, avatar, verified, verification_code)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    _execute(user_query, (email, password, username, '0', '0', verified, verification_code))
    user = user_information(email)
    if user is None:
        return 'Error: the user was not created'
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    f_query = """
        INSERT INTO fundamentals(user_id, testsPassed, totalTests, lastActivity)
        VALUES (%s, %s, %s, %s)
    """
    a_query = """
        INSERT INTO algorithms(user_id, testsPassed, totalTests, lastActivity)
        VALUES (%s, %s, %s, %s)
    """
    _execute(f_query, (user['id'], 0, 0, current_time))
    _execute(a_query, (user['id'], 0, 0, current_time))
    return 'success'

def change_db_users(email, *args):
    valid_columns = ['password', 'username', 'achievement', 'avatar', 'verified', 'verification_code']
    for column, new_value in args:
        if column not in valid_columns:
            return f"Error: Invalid column name {column}"
        query = f"UPDATE users SET {column} = %s WHERE email = %s"
        _execute(query, (new_value, email))
    return 'success'


def user_information(email):
    query = "SELECT id, email, password, username, achievement, avatar, verified, verification_code FROM users WHERE email = %s"
    row = _execute(query, (email,), fetchone=True)
    if not row:
        return None
    keys = ['id', 'email', 'password', 'username', 'achievement', 'avatar', 'verified', 'verification_code']
    return dict(zip(keys, row))
