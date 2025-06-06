from fastapi import APIRouter, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from services.leaderboard_service import get_leaderboard
from services.achievement_service import check_and_award

router = APIRouter()


@router.get("/leaderboard")
async def leaderboard(background_tasks: BackgroundTasks):
    """Returns the fundamentals and algorithms leaderboards and awards top‑3 badges asynchronously."""
    data = await run_in_threadpool(get_leaderboard)
    for category in ('fundamentals', 'algorithms'):
        for entry in data.get(category, [])[:3]:
            user_id = entry.get('user_id')
            if user_id:
                background_tasks.add_task(
                    check_and_award, user_id, 'leaderboard_top3')
    return data
