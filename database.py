# import pymysql
# import json
# from dbutils.pooled_db import PooledDB
# import redis
# from sqlalchemy import text
# from local_db import SessionLocal
#
# # new database module for shared DB pool and Redis client
# with open('database_user.json') as file:
#     _cfg = json.load(file)
#
# pool = PooledDB(
#     creator=pymysql,
#     host=_cfg['host'],
#     user=_cfg['user'],
#     password=_cfg['password'],
#     database=_cfg['database'],
#     autocommit=True,
#     mincached=5,
#     maxcached=20,
# )
#
# redis_client = redis.Redis()
# LOGIN_ATTEMPT_LIMIT = 5
# BLOCK_TIME_MINUTES = 15
#
#
# def execute(query: str, params: tuple = None, fetchone: bool = False):
#     conn = pool.connection()
#     cur = conn.cursor()
#     cur.execute(query, params or ())
#     result = cur.fetchone() if fetchone else cur.fetchall()
#     cur.close()
#     conn.close()
#     return result
#
# #
# # def execute(query: str, params: tuple = None, fetchone: bool = False):
# #     db = SessionLocal()
# #     try:
# #         result = db.execute(query, params or {})
# #         if fetchone:
# #             return result.fetchone()
# #         return result.fetchall()
# #     finally:
# #         db.close()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import os
import redis

# Настройка базы данных
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Функция execute для обратной совместимости
def execute(query: str, params=None, fetchone=False):
    db = SessionLocal()
    try:
        result = db.execute(text(query), params or {})
        if fetchone:
            return result.fetchone()
        return result.fetchall()
    finally:
        db.close()


# Настройка Redis (с заглушкой при недоступности)
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0))
    )
    redis_client.ping()  # Проверка подключения
except redis.ConnectionError:
    class RedisStub:
        def get(self, *args, **kwargs): return None

        def setex(self, *args, **kwargs): pass

        def exists(self, *args, **kwargs): return False

        def incr(self, *args, **kwargs): return 1

        def delete(self, *args, **kwargs): pass


    redis_client = RedisStub()
    print("Redis not available, using stub")

LOGIN_ATTEMPT_LIMIT = 5
BLOCK_TIME_MINUTES = 15