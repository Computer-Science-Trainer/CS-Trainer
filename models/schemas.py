from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
    

class AchievementOut(BaseModel):
    code: str
    emoji: str
    unlocked_at: Optional[datetime]
    

class SuggestionOut(BaseModel):
    id: int
    user_id: int
    title: str
    question_text: str
    question_type: str
    options: List[str]
    correct_answer: str
    topic_code: str
    status: str
    created_at: datetime
    admin_comment: Optional[str] = None