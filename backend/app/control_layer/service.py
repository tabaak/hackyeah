import io
import json
import re
import time
from datetime import datetime, timedelta, timezone

from .gateway import Gateway, SECRET, measurements
from .models import (AssessmentRequest, Evidence, Extraction, PolicyMatch, PolicyStructure, Risk,
                     SECTORS, highest, risk_category)
from .providers import ProviderError
from .store import now, digest


def chunks(text, size=1800, overlap=200):
    return [text[i:i + size] for i in range(0, len(text), size - overlap) if text[i:i + size].strip()]


def references_valid(refs, evidence):
    return bool(refs) and all(r.evidence_id in evidence and r.quote in evidence[r.evidence_id].content for r in refs)


def validate_structure(structure, text):
    ids = [c.id for c in structure.clauses]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate policy clause IDs")
    for c in structure.clauses:
        phrases = [c.text, *c.remediation, *c.required_evidence, *[s for e in c.exceptions for s in e.conditions]]
        if any(not p.strip() or p not in text for p in phrases):
            raise ValueError("Policy rule not grounded in source")
        if any(k not in ("all", "deal", "investigation", "scandal", "operational_crisis", "data_breach", "regulatory", "other") for k in c.applies_to):
            raise ValueError("Invalid applicability")
        ex_ids = [e.id for e in c.exceptions]
        if len(ex_ids) != len(set(ex_ids)):
            raise ValueError("Duplicate exception IDs")


class Service:
    def __init__(self, config, store, providers, source):
        self.config, self.store, self.providers, self.source = config, store, providers, source

    def gateway(self, org, jid):
        return Gateway(self.config, self.providers, self.store, org, jid)

    def remember_company(self, org, company):
        old = self.store.get(org, company["id"], "company")
        if old:
            company = {**company, "sector": old["data"]["sector"]}
        self.store.put(org, "company", company, company["id"], "internal", company["id"])
        return company

    def classify_text(self, gateway, text, doc_id, minimum, origin="document"):
        if not text.strip() or len(text) > 60000:
            raise ValueError("Document must contain 1..60000 extracted characters")
        floor = highest("internal", minimum)
        evidence, findings = [], []
        for n, content in enumerate(chunks(text)):
            e = Evidence(id=f"{doc_id}:{n}", content=content, classification=floor, origin=origin)
            scan = gateway.sensitivity(e)
            evidence.append(e)
            findings.extend({"evidenceId": e.id, **f.wire()} for f in scan.findings)
        classification = highest(floor, *(e.classification for e in evidence))
        # Whole-document taint: no apparently innocuous chunk may downgrade a restricted document.
        for e in evidence:
            e.classification = classification
        return evidence, findings, classification

    def process_document(self, org, jid):
        job = self.store.job(org, jid)
        self.store.update_job(org, jid, "running")
        try:
            record = self.store.get(org, jid, "document")
            meta = record["data"]
            with open(meta["path"], "rb") as f:
                data = f.read()
            if meta["name"].lower().endswith(".pdf"):
                from pypdf import PdfReader
                text = "\n\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
            else:
                text = data.decode("utf-8", errors="strict")
            evidence, findings, level = self.classify_text(self.gateway(org, jid), text, jid, meta["minimum"])
            self.store.add_chunks(org, job["company"], jid, evidence)
            meta.update(status="ready", findings=findings, chunkCount=len(evidence))
            self.store.put(org, "document", meta, job["company"], level, jid)
            self.store.update_job(org, jid, "succeeded", {"documentId": jid, "classification": level,
                                  "chunkCount": len(evidence), "findings": findings}, level)
        except Exception:
            self.store.update_job(org, jid, "failed", error="document_processing_failed")

    def process_policy(self, org, jid):
        self.store.update_job(org, jid, "running")
        try:
            row = self.store.get(org, jid, "policy")
            data = row["data"]
            gateway = self.gateway(org, jid)
            evidence, findings, level = self.classify_text(gateway, data["text"], jid, data["minimum"], "policy")
            structure = gateway.reason("policy_structure", {"source": data["text"]}, PolicyStructure)
            validate_structure(structure, data["text"])
            data.update(status="draft", structure=structure.wire(), findings=findings,
                        sourceHash=digest(data["text"]), version=1)
            self.store.put(org, "policy", data, classification=level, record_id=jid)
            self.store.update_job(org, jid, "succeeded", {"policyId": jid, "status": "draft", "version": 1,
                                  "classification": level}, level)
        except Exception:
            self.store.update_job(org, jid, "failed", error="policy_processing_failed")

    def activate_policy(self, org, pid, structure, user_id):
        row = self.store.get(org, pid, "policy")
        if not row or row["data"].get("status") != "draft":
            raise ValueError("Policy must be an existing processed draft")
        validate_structure(structure, row["data"]["text"])
        data = {**row["data"], "structure": structure.wire(), "status": "active",
                "activatedBy": user_id, "activatedAt": now(), "structureHash": digest(structure.wire())}
        self.store.put(org, "policy", data, classification=row["classification"], record_id=pid)
        return {"id": pid, "version": data["version"], "status": "active", "structureHash": data["structureHash"]}

    def policy_review(self, gateway, policy, events, risk, evidence):
        if not policy or policy["data"].get("status") != "active":
            return {"status": "review_required", "reason": "No activated policy", "requiredRole": "compliance"}
        data = policy["data"]
        structure = PolicyStructure.model_validate(data["structure"])
        kinds = {e.kind for e in events}
        deterministic = {c.id for c in structure.clauses if "all" in c.applies_to or kinds.intersection(c.applies_to)}
        try:
            matches = gateway.reason("policy_match", {"clauses": structure.wire()["clauses"],
                                     "events": [e.wire() for e in events], "risk": risk.wire()}, PolicyMatch)
            known = {c.id for c in structure.clauses}
            if set(matches.clause_ids) - known:
                raise ProviderError("unknown_policy_clause")
            selected = deterministic | set(matches.clause_ids)
        except ProviderError:
            return {"status": "review_required", "reason": "Policy interpretation needs human review",
                    "policyId": policy["id"], "policyVersion": data["version"], "requiredRole": "compliance"}
        clauses = [c for c in structure.clauses if c.id in selected]
        if not clauses:
            status = "review_required"
        elif any(c.effect == "prohibition" and not c.exceptions for c in clauses):
            status = "remediation_required"
        elif any(c.exceptions for c in clauses):
            status = "conditional_path_proposed"
        else:
            status = "remediation_required"
        # All executable recommendation text comes from human-activated rules, never model prose.
        return {"status": status, "policyId": policy["id"], "policyVersion": data["version"],
                "sourceHash": data["sourceHash"], "structureHash": data["structureHash"],
                "clauses": [c.wire() for c in clauses], "requiredRole": "compliance",
                "conditionsVerified": False, "originalRiskScore": risk.risk_score,
                "clientDecision": "not_made"}

    def run_assessment(self, org, jid):
        job = self.store.job(org, jid)
        start = time.perf_counter()
        self.store.update_job(org, jid, "running")
        try:
            request = AssessmentRequest.model_validate(job["request"])
            company = self.source.company(org, job["company"])
            if not company:
                raise ValueError("Company unavailable")
            company = self.remember_company(org, company)
            policy = self.store.get(org, request.policy_id, "policy") if request.policy_id else None
            if request.policy_id and (not policy or (policy["classification"] == "restricted" and job["role"] != "compliance")):
                raise ValueError("Policy unavailable")
            # Snapshot policy at start; no changes to recommendations mid-run.
            level = highest("internal", policy["classification"] if policy else "internal")
            cutoff = datetime.now(timezone.utc) - timedelta(days=request.days)
            feed, truncated = self.source.mentions(org, job["company"], cutoff.isoformat(), self.config.max_items)
            gateway = self.gateway(org, jid)
            events, evidence_map, decisions, gaps, seen = [], {}, [], [], set()
            excluded, failures = 0, 0
            if truncated:
                gaps.append("Source import capped at 100 mentions; additional material was not assessed")
            docs = self.store.records(org, "document", job["company"])
            if any(d["data"].get("status") != "ready" for d in docs):
                gaps.append("Some documents have not completed local processing")
            if job["role"] != "compliance" and any(d["classification"] == "restricted" for d in docs):
                gaps.append("Some evidence is outside the caller's access level")
            for article in feed:
                # Exact normalized text dedupe; semantic event dedupe happens after extraction.
                key = digest(re.sub(r"\s+", " ", article.content).strip().lower())
                if key in seen:
                    decisions.append({"evidenceId": article.id, "pass": False, "reason": "duplicate"})
                    continue
                seen.add(key)
                # Bound each model request without silently truncating long articles.
                if len(article.content) > 12000:
                    gaps.append("An oversized article requires separate review")
                    failures += 1
                    continue
                if SECRET.search(article.content):
                    article.classification = highest(article.classification, "confidential")
                    try:
                        gateway.sensitivity(article)
                    except ProviderError:
                        article.classification = "restricted"
                level = highest(level, article.classification)
                decision = ({"pass": True, "reason": "baseline", "provider": "none"} if request.baseline
                            else gateway.decide(article, company))
                level = highest(level, article.classification)
                decisions.append({"evidenceId": article.id, **decision})
                # Store rejected material locally for replay with baseline=true.
                self.store.put(org, "material", article.wire(), job["company"], article.classification,
                               record_id=digest([org, job["company"], article.id]))
                if not decision["pass"]:
                    excluded += 1
                    continue
                hits = self.store.search(org, job["company"], article.content, job["role"])
                context = [article] + [Evidence(id=h["evidence"], content=h["content"], classification=h["classification"]) for h in hits]
                for e in context:
                    evidence_map[e.id] = e
                    level = highest(level, e.classification)
                try:
                    extracted = gateway.reason("extract", {"company": company, "evidence": [e.wire() for e in context]}, Extraction)
                    for event in extracted.events if extracted.relevant else []:
                        if not references_valid(event.references, evidence_map):
                            raise ProviderError("invalid_event_reference")
                        for claim in event.claims:
                            valid = references_valid(claim.references, evidence_map)
                            independent = any(evidence_map[r.evidence_id].independent for r in claim.references if r.evidence_id in evidence_map)
                            if not valid or not independent:
                                claim.verdict = "insufficient_evidence"
                                claim.references = [r for r in claim.references if references_valid([r], evidence_map)]
                                claim.limitations.append("Not independently corroborated by the supplied evidence")
                        if event.occurred_at:
                            try:
                                parsed = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
                                if parsed.tzinfo is None:
                                    raise ValueError("Event timestamp must include timezone")
                            except ValueError:
                                event.occurred_at = None
                        events.append(event)
                except ProviderError:
                    failures += 1
                    gaps.append("Some material could not be reliably interpreted")
            unique_events = {}
            for event in events:
                key = re.sub(r"\W+", " ", event.event_key.lower()).strip()
                if key not in unique_events:
                    unique_events[key] = event
                else:
                    known = {(r.evidence_id, r.quote) for r in unique_events[key].references}
                    unique_events[key].references.extend(r for r in event.references if (r.evidence_id, r.quote) not in known)
            events = list(unique_events.values())
            # Keep final inference bounded; explicitly mark omitted context rather than pretending full coverage.
            final_evidence = list(evidence_map.values())[:30]
            if len(evidence_map) > 30:
                gaps.append("Final synthesis limited to 30 evidence fragments")
            risk = Risk(risk_score=None, coverage_sufficient=False, rationale="Insufficient evidence", references=[], gaps=[])
            if events:
                risk = gateway.reason("risk", {"company": company, "events": [e.wire() for e in events],
                                      "evidence": [e.wire() for e in final_evidence], "coverageGaps": gaps,
                                      "rubricVersion": "palladion-risk-v1"}, Risk)
                independent = any(evidence_map[r.evidence_id].independent for r in risk.references if r.evidence_id in evidence_map)
                if not references_valid(risk.references, {e.id: e for e in final_evidence}) or not independent:
                    risk.coverage_sufficient = False
                    risk.references = [r for r in risk.references if references_valid([r], {e.id: e for e in final_evidence})]
                    gaps.append("Risk score lacks independent, valid supporting references")
            if not risk.coverage_sufficient or failures or gaps:
                risk.risk_score = None
                risk.coverage_sufficient = False
            risk.gaps = list(dict.fromkeys([*risk.gaps, *gaps]))
            review = {"status": "insufficient_evidence" if risk.risk_score is None else "review_required",
                      "requiredRole": "compliance", "clientDecision": "not_made"}
            if risk.risk_score is not None and risk.risk_score >= 7:
                review = self.policy_review(gateway, policy, events, risk, evidence_map)
            gateway.audit(operation="assessment_decision", status="proposed",
                          riskCategory=risk_category(risk.risk_score), rubricVersion="palladion-risk-v1",
                          classification=level, clientDecision="not_made")
            gateway.audit(operation="policy_review", status=review["status"],
                          policyId=review.get("policyId"), policyVersion=review.get("policyVersion"),
                          clauseIds=[c["id"] for c in review.get("clauses", [])], requiredRole="compliance")
            recent = datetime.now(timezone.utc) - timedelta(hours=72)
            def is_recent(event):
                stamps = [event.occurred_at] if event.occurred_at else []
                # Published date is not a substitute for an unknown event date.
                return any(recent <= datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc)
                           <= datetime.now(timezone.utc) for t in stamps)
            result = {"companyId": company["id"], "companyName": company["name"], "sector": company["sector"],
                      "purpose": request.purpose, "assessedAt": now(), "periodDays": request.days,
                      "rubricVersion": "palladion-risk-v1", **risk.wire(),
                      "riskCategory": risk_category(risk.risk_score),
                      "assessmentStatus": "complete" if risk.risk_score is not None else "insufficient_evidence",
                      "classification": level, "events": [e.wire() for e in events],
                      "activeCrisisEvents": sum(e.kind in {"operational_crisis", "data_breach", "scandal"} and is_recent(e) for e in events),
                      "policyReview": review, "gateDecisions": decisions,
                      "coverage": {"imported": len(feed), "unique": len(seen), "excluded": excluded,
                                   "sourceCapped": truncated, "failedMaterials": failures},
                      "evidence": [e.wire() for e in evidence_map.values()],
                      "metrics": measurements(self.store.audits(org, jid), self.config.pricing),
                      "durationMs": round((time.perf_counter() - start) * 1000, 2),
                      "mode": getattr(self.providers["qwen"], "mode", "live")}
            self.store.update_job(org, jid, "succeeded", result, level)
        except Exception:
            self.store.update_job(org, jid, "failed", error="assessment_failed")

    def sector_summary(self, org, role):
        companies = self.store.records(org, "company")
        latest = {j["company"]: j for j in self.store.latest_assessments(org)}
        summaries = {s: {"sector": s, "companies": 0, "low": 0, "medium": 0, "high": 0,
                         "unknown": 0, "activeCrisisEvents": 0} for s in SECTORS}
        for company in companies:
            row = summaries[company["data"]["sector"]]
            row["companies"] += 1
            job = latest.get(company["id"])
            if not job or (job["classification"] == "restricted" and role != "compliance"):
                row["unknown"] += 1
            else:
                row[job["result"]["riskCategory"]] += 1
                row["activeCrisisEvents"] += job["result"]["activeCrisisEvents"]
        return {"scope": "locally_tracked_companies_only", "sectors": list(summaries.values())}
