from fastapi import APIRouter
from services.leaderboard_service import get_leaderboard

router = APIRouter()


@router.get("/leaderboard")
def leaderboard():
    """Returns the fundamentals and algorithms leaderboards."""
    return get_leaderboard()