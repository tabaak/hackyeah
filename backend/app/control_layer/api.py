"""Run with ONE worker on the trusted inference host, bound to 127.0.0.1:8002."""
import fcntl
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.deps import get_current_user, require_compliance
from app.schemas.auth import CurrentUser

from .config import Settings
from .models import AssessmentRequest, Classification, PolicyCreate, PolicyStructure, SECTORS, SectorUpdate, highest
from .providers import providers
from .service import Service
from .source import SupabaseSource
from .store import Conflict, Store


def create_app(service=None):
    @asynccontextmanager
    async def lifespan(app):
        if app.state.service is None:
            config = Settings()
            app.state.service = Service(config, Store(config.data_dir), providers(config), SupabaseSource())
        store = app.state.service.store
        lockpath = store.root / "server.lock"
        fd = os.open(lockpath, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            store.recover()
            app.state.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="control")
            yield
            app.state.executor.shutdown(wait=True)
        finally:
            os.close(fd)

    app = FastAPI(title="Palladion Local AI Control Layer", version="0.1.0", lifespan=lifespan)
    app.state.service = service

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        # Default FastAPI errors echo request input, including potentially secret strings.
        return JSONResponse(status_code=422, content={"detail": "invalid_request"})

    @app.exception_handler(Conflict)
    async def conflict(_request, _exc):
        return JSONResponse(status_code=409, content={"detail": "idempotency_or_record_conflict"})

    @app.exception_handler(Exception)
    async def unexpected(_request, _exc):
        return JSONResponse(status_code=503, content={"detail": "local_service_unavailable"})

    router = APIRouter(prefix="/api/v1/control", dependencies=[Depends(get_current_user)])

    def svc():
        return app.state.service

    def company(org, cid):
        try:
            row = svc().source.company(org, cid)
        except Exception:
            raise HTTPException(503, "company_source_unavailable") from None
        if not row:
            raise HTTPException(404, "company_not_found")
        return svc().remember_company(org, row)

    def visible_record(user, rid, kind):
        row = svc().store.get(user.organization_id, rid, kind)
        if not row or (row["classification"] == "restricted" and user.role != "compliance"):
            raise HTTPException(404, "record_not_found")
        return row

    def visible_job(user, jid, kind=None, audit=False):
        job = svc().store.job(user.organization_id, jid)
        if not job or (kind and job["kind"] != kind):
            raise HTTPException(404, "job_not_found")
        if job["classification"] == "restricted" and user.role != "compliance" and (job["state"] == "succeeded" or audit):
            raise HTTPException(403, "compliance_required")
        return job

    def job_payload(job):
        return {"id": job["id"], "kind": job["kind"], "state": job["state"],
                "result": job["result"], "error": job["error"], "updatedAt": job["updated"]}

    @router.get("/providers/status")
    def provider_status(user: CurrentUser = Depends(get_current_user)):
        return {"mode": "live", "providers": [p.status() for p in svc().providers.values()]}

    @router.get("/jobs/{jid}")
    def get_job(jid: str, user: CurrentUser = Depends(get_current_user)):
        return job_payload(visible_job(user, jid))

    @router.get("/companies")
    def companies(sector: str | None = None, user: CurrentUser = Depends(get_current_user)):
        if sector and sector not in SECTORS:
            raise HTTPException(422, "unknown_sector")
        return [r["data"] for r in svc().store.records(user.organization_id, "company")
                if not sector or r["data"]["sector"] == sector]

    @router.put("/companies/{cid}/sector")
    def update_sector(cid: str, body: SectorUpdate, user: CurrentUser = Depends(get_current_user)):
        if body.sector not in SECTORS:
            raise HTTPException(422, "unknown_sector")
        row = company(user.organization_id, cid)
        row["sector"] = body.sector
        svc().store.put(user.organization_id, "company", row, cid, "internal", cid)
        return row

    @router.post("/companies/{cid}/documents", status_code=202)
    async def upload_document(cid: str, file: UploadFile = File(...),
                              classification: Classification = Form("confidential"),
                              idempotency_key: str = Header(..., min_length=1, max_length=200),
                              user: CurrentUser = Depends(get_current_user)):
        company(user.organization_id, cid)
        name = Path(file.filename or "document.txt").name[:200]
        if Path(name).suffix.lower() not in {".pdf", ".txt"}:
            raise HTTPException(422, "pdf_or_utf8_txt_required")
        data = await file.read(5 * 1024 * 1024 + 1)
        if not data or len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, "document_size_limit")
        minimum = highest("internal", classification)
        if minimum == "restricted" and user.role != "compliance":
            raise HTTPException(403, "compliance_required")
        request = {"name": name, "minimum": minimum, "sha256": hashlib.sha256(data).hexdigest()}
        jid, fresh = svc().store.create_job(user.organization_id, "document", cid, user.role, request, idempotency_key)
        if fresh:
            path = svc().store.save_file(data)
            svc().store.put(user.organization_id, "document", {**request, "path": path, "status": "processing"}, cid, "restricted", jid)
            app.state.executor.submit(svc().process_document, user.organization_id, jid)
        return {"jobId": jid, "documentId": jid, "state": svc().store.job(user.organization_id, jid)["state"]}

    @router.post("/policies", status_code=202)
    def create_policy(body: PolicyCreate, idempotency_key: str = Header(..., min_length=1, max_length=200),
                      user: CurrentUser = Depends(require_compliance)):
        request = body.wire()
        jid, fresh = svc().store.create_job(user.organization_id, "policy", "", user.role, request, idempotency_key)
        if fresh:
            # A new source is a new immutable version ID; active versions are never overwritten.
            svc().store.put(user.organization_id, "policy", {"name": body.name, "text": body.text,
                            "minimum": highest("internal", body.classification), "status": "processing"},
                            classification="restricted", record_id=jid)
            app.state.executor.submit(svc().process_policy, user.organization_id, jid)
        return {"jobId": jid, "policyId": jid, "state": svc().store.job(user.organization_id, jid)["state"]}

    @router.get("/policies/{pid}")
    def get_policy(pid: str, user: CurrentUser = Depends(require_compliance)):
        row = visible_record(user, pid, "policy")
        return {"id": pid, "classification": row["classification"], **row["data"]}

    @router.post("/policies/{pid}/activate")
    def activate_policy(pid: str, body: PolicyStructure, user: CurrentUser = Depends(require_compliance)):
        visible_record(user, pid, "policy")
        try:
            return svc().activate_policy(user.organization_id, pid, body, user.id)
        except ValueError:
            raise HTTPException(422, "policy_not_draft_or_rules_not_grounded") from None

    @router.post("/companies/{cid}/assessments", status_code=202)
    def assess(cid: str, body: AssessmentRequest, idempotency_key: str = Header(..., min_length=1, max_length=200),
               user: CurrentUser = Depends(get_current_user)):
        company(user.organization_id, cid)
        if body.policy_id:
            visible_record(user, body.policy_id, "policy")
        jid, fresh = svc().store.create_job(user.organization_id, "assessment", cid, user.role, body.wire(), idempotency_key)
        if fresh:
            app.state.executor.submit(svc().run_assessment, user.organization_id, jid)
        else:
            visible_job(user, jid, "assessment")
        return {"id": jid, "jobId": jid, "state": svc().store.job(user.organization_id, jid)["state"]}

    @router.get("/assessments/{jid}")
    def assessment(jid: str, user: CurrentUser = Depends(get_current_user)):
        return job_payload(visible_job(user, jid, "assessment"))

    @router.get("/assessments/{jid}/audit")
    def audit(jid: str, user: CurrentUser = Depends(get_current_user)):
        visible_job(user, jid, "assessment", audit=True)
        return {"assessmentId": jid, "events": svc().store.audits(user.organization_id, jid)}

    @router.get("/sectors")
    def sectors():
        return {"sectors": SECTORS}

    @router.get("/sectors/summary")
    def sector_summary(sector: str | None = None, user: CurrentUser = Depends(get_current_user)):
        result = svc().sector_summary(user.organization_id, user.role)
        if sector:
            if sector not in SECTORS:
                raise HTTPException(422, "unknown_sector")
            result["sectors"] = [s for s in result["sectors"] if s["sector"] == sector]
        return result

    @app.get("/health")
    def health():
        return {"status": "ok", "storage": "local", "mode": "live"}

    app.include_router(router)
    return app


app = create_app()
