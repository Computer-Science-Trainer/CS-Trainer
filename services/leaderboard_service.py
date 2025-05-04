import json
from database import execute, redis_client


def get_leaderboard(number_of_users: int = 10) -> dict:
    cache_key = f"leaderboard:{number_of_users}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
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
    fund_data = execute(fund_query, (number_of_users,))
    alg_data = execute(alg_query, (number_of_users,))

    fundamentals = [
        {
            'user_id': r[1], 'score': r[2], 'testsPassed': r[3],
            'totalTests': r[4], 'lastActivity': r[5],
            'username': r[6], 'achievement': r[7], 'avatar': r[8]
        }
        for r in fund_data
    ]
    algorithms = [
        {
            'user_id': r[1], 'score': r[2], 'testsPassed': r[3],
            'totalTests': r[4], 'lastActivity': r[5],
            'username': r[6], 'achievement': r[7], 'avatar': r[8]
        }
        for r in alg_data
    ]

    result = {'fundamentals': fundamentals, 'algorithms': algorithms}
    redis_client.setex(cache_key, 60, json.dumps(result, default=str))
    return result
