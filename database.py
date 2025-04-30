import pymysql
import json
from dbutils.pooled_db import PooledDB
import redis

# new database module for shared DB pool and Redis client
with open('database_user.json') as file:
    _cfg = json.load(file)

pool = PooledDB(
    creator=pymysql,
    host=_cfg['host'],
    user=_cfg['user'],
    password=_cfg['password'],
    database=_cfg['database'],
    autocommit=True,
    mincached=5,
    maxcached=20,
)

redis_client = redis.Redis()


def execute(query: str, params: tuple = None, fetchone: bool = False):
    conn = pool.connection()
    cur = conn.cursor()
    cur.execute(query, params or ())
    result = cur.fetchone() if fetchone else cur.fetchall()
    cur.close()
    conn.close()
    return result
