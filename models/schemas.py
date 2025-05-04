from pydantic import BaseModel
from datetime import datetime


class UserOut(BaseModel):
    id: int
    email: str
    username: str


class AchievementOut(BaseModel):
    name: str
    title: str
    description: str
    unlocked_at: datetime
    icon: str