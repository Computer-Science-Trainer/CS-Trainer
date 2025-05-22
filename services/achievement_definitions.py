from typing import Any, Dict

ACHIEVEMENT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "first_login": {
        "emoji": "👋",
        "event": "login",
    },
    "leaderboard_top3": {
        "emoji": "🏅",
        "event": "leaderboard_top3",
    },
    "passed_10_answers": {
        "emoji": "🎉",
        "threshold": 10
    },
    "score_50": {
        "emoji": "🥈",
        "threshold": 50
    },
    "score_100": {
        "emoji": "🥇",
        "threshold": 100
    },
    "score_200": {
        "emoji": "🏆",
        "threshold": 200
    }
}
