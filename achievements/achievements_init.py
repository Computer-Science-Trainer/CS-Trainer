from models.db_models import AchievementTemplate
from database import SessionLocal
from achievements.achievements_config import ACHIEVEMENTS


def init_achievement_templates():
    db = SessionLocal()
    try:
        for name, data in ACHIEVEMENTS.items():
            if not db.query(AchievementTemplate).filter_by(name=name).first():
                template = AchievementTemplate(
                    name=name,
                    title=data["title"],
                    description=data["description"],
                    icon=data["icon"]
                )
                db.add(template)
        db.commit()
    finally:
        db.close()