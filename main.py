from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
import os
from sqlalchemy import MetaData
from routers.auth_router import router as auth_router
from routers.user_router import router as user_router
from routers.leaderboard_router import router as leaderboard_router
from routers.oauth_router import router as oauth_router
from routers.tests.test_router import router as tests_router
from achievements.achievements_init import init_achievement_templates
from database import Base, engine
from security import bearer_scheme

Base.metadata.create_all(bind=engine)

metadata = MetaData()
metadata.reflect(bind=engine)
app = FastAPI(
    title="CS-Trainer API",
    version="1.0.0",
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "persistAuthorization": True  # Сохраняет токен между запросами
    }
)

# Add session middleware for OAuthlib
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY")
    )
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization"],  # Разрешаем заголовок
    expose_headers=["Authorization"]
)

app.include_router(auth_router, prefix="/auth")
app.include_router(oauth_router, prefix="/api/auth")
app.include_router(
    user_router,
    dependencies=[Depends(bearer_scheme)]  # Применяется ко всем эндпоинтам роутера
)
app.include_router(leaderboard_router, prefix="/api")
app.include_router(tests_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    init_achievement_templates()


# Точка входа в приложение
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)