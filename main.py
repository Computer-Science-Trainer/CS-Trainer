from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
import os
from routers.auth_router import router as auth_router
from routers.user_router import router as user_router
from routers.leaderboard_router import router as leaderboard_router
from routers.oauth_router import router as oauth_router
from routers.topics_router import router as topics_router
from routers.admin_router import router as admin_router
from routers.test_router import router as test_router

app = FastAPI()

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
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth_router, prefix="/api/auth")
app.include_router(oauth_router, prefix="/api/auth")
app.include_router(user_router, prefix="/api")
app.include_router(leaderboard_router, prefix="/api")
app.include_router(topics_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(test_router, prefix="/api/tests")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
