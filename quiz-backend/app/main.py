from fastapi import FastAPI
from .core.config import settings
from .core.cors import setup_cors
from .api.v1.routers import quizzes as quizzes_router

app = FastAPI(title=settings.APP_NAME)
setup_cors(app)

app.include_router(quizzes_router.router, prefix=settings.API_V1_PREFIX)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}