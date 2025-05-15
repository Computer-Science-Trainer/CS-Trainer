import pymysql
import json
from dbutils.pooled_db import PooledDB
import redis
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


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


_sqlalchemy_db_url = f"mysql+pymysql://{_cfg['user']}:{_cfg['password']}@{_cfg['host']}/{_cfg['database']}"
_engine = create_engine(_sqlalchemy_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base = declarative_base()