from fastapi import APIRouter, Depends, FastAPI

from app.deps import get_current_user
from app.routers import analytics, auth, companies, documents, feed, notifications, response, sources

app = FastAPI(title="ProofGate API", version="0.1.0", description="Skeleton: all endpoints return 501 until implemented.")

api = APIRouter(prefix="/api/v1")
for module in (auth, companies, documents, feed, response, analytics, notifications):
    api.include_router(module.router, dependencies=[Depends(get_current_user)])
# Sources: the Meta webhook authenticates by provider signature, so auth is set per route there.
api.include_router(sources.router)
app.include_router(api)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
