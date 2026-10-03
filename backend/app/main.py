from fastapi import APIRouter, FastAPI

from app.routers import analytics, auth, documents, feed, incidents, notifications, sources

app = FastAPI(title="ProofGate API", version="0.1.0", description="Skeleton: all endpoints return 501 until implemented.")

api = APIRouter(prefix="/api/v1")
for module in (auth, documents, sources, feed, incidents, analytics, notifications):
    api.include_router(module.router)
app.include_router(api)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
