import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.deps import get_current_user
from app.routers import analytics, auth, companies, documents, feed, notifications, push, response, sources
from app.services import demo

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(demo.live_loop()) if settings.demo_live_interval_s > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Palladion API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

api = APIRouter(prefix="/api/v1")
for module in (auth, companies, documents, feed, response, analytics, notifications, push):
    api.include_router(module.router, dependencies=[Depends(get_current_user)])
# Sources: the Meta webhook authenticates by provider signature, so auth is set per route there.
api.include_router(sources.router)
app.include_router(api)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
