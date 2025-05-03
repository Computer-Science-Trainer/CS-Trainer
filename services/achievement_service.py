from typing import Dict, Any
from database import execute, redis_client
from services.achievement_definitions import ACHIEVEMENT_DEFINITIONS
import json
from pymysql.err import IntegrityError


def sync_definitions() -> None:
    rows = execute("SELECT code FROM achievements")
    existing = {row[0] for row in rows}
    for code, defn in ACHIEVEMENT_DEFINITIONS.items():
        if code not in existing:
            execute(
                "INSERT INTO achievements(code, emoji) VALUES (%s, %s)",
                (code, defn.get('emoji', ''))
            )


def get_definitions() -> Dict[str, Dict[str, Any]]:
    cached = redis_client.get("achievements:definitions")
    if cached:
        return json.loads(cached)
    sync_definitions()
    rows = execute(
        "SELECT id, code, emoji FROM achievements ORDER BY id"
    )
    defs = {
        row[1]: {'id': row[0], 'code': row[1], 'emoji': row[2]}
        for row in rows
    }
    redis_client.setex("achievements:definitions", 15, json.dumps(defs))
    return defs


def award_achievement(user_id: int, code: str) -> bool:
    defs = get_definitions()
    if code not in defs:
        return False
    ach_id = defs[code]['id']
    exists = execute(
        "SELECT 1 FROM user_achievements WHERE user_id=%s AND achievement_id=%s",
        (user_id, ach_id), fetchone=True
    )
    if exists:
        return False
    try:
        execute(
            "INSERT INTO user_achievements(user_id, achievement_id) VALUES (%s, %s)",
            (user_id, ach_id)
        )
        return True
    except IntegrityError:
        return False


def get_user_achievements(user_id: int) -> list[dict]:
    cache_key = f"user:{user_id}:achievements"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    rows = execute(
        "SELECT ua.unlocked_at, a.code, a.emoji"
        " FROM user_achievements ua"
        " JOIN achievements a ON ua.achievement_id = a.id"
        " WHERE ua.user_id = %s"
        " ORDER BY ua.unlocked_at",
        (user_id,)
    )
    result = []
    for r in rows:
        result.append({
            'code': r[1],
            'emoji': r[2],
            'unlocked_at': r[0]
        })
    cache_list = []
    for a in result:
        item = a.copy()
        if item['unlocked_at'] is not None:
            item['unlocked_at'] = item['unlocked_at'].isoformat()
        cache_list.append(item)
    redis_client.setex(cache_key, 15, json.dumps(cache_list))
    return result


def check_and_award(user_id: int, event: str = None,
                    tests_passed: int = None) -> list[str]:
    awarded = []
    for code, defn in ACHIEVEMENT_DEFINITIONS.items():
        if event and defn.get('event') == event:
            if award_achievement(user_id, code):
                awarded.append(code)
        if tests_passed is not None and 'threshold' in defn:
            if tests_passed >= defn['threshold']:
                if award_achievement(user_id, code):
                    awarded.append(code)
    return awarded
