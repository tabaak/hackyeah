"""Reproducible synthetic corpus: fixture and live inference are explicitly separate modes."""
import argparse
import json
import tempfile
import uuid
from pathlib import Path

from .config import Settings
from .fixtures import (BANK_POLICY, COMPANY, DEFENCE_POLICY, ORG, SECRET_DOCUMENT,
                       FixtureSource, fixture_providers)
from .models import AssessmentRequest, Evidence, PolicyStructure
from .providers import providers
from .service import Service
from .store import Store

CASES = ("namesake", "deal", "conditional", "remediation", "secret_injection")


def prepare_policy(service, policy):
    jid, _ = service.store.create_job(ORG, "policy", "", "compliance", {"name": policy["name"]}, str(uuid.uuid4()))
    service.store.put(ORG, "policy", {"name": policy["name"], "text": policy["text"], "minimum": "confidential", "status": "processing"},
                      classification="restricted", record_id=jid)
    service.process_policy(ORG, jid)
    if service.store.job(ORG, jid)["state"] != "succeeded":
        raise RuntimeError("policy_processing_failed")
    # Fixture policy clauses have been manually prepared against these exact fictional texts.
    service.activate_policy(ORG, jid, PolicyStructure(clauses=policy["clauses"]), "fictional-compliance-reviewer")
    return jid


def run_case(service, case, baseline=False):
    service.source = FixtureSource(case)
    policy = DEFENCE_POLICY if case == "remediation" else BANK_POLICY
    policy_id = prepare_policy(service, policy)
    if case == "secret_injection":
        docid, _ = service.store.create_job(ORG, "document", COMPANY["id"], "compliance", {}, str(uuid.uuid4()))
        path = service.store.save_file(SECRET_DOCUMENT.encode())
        service.store.put(ORG, "document", {"name": "FICTIONAL-secret.txt", "path": path, "minimum": "restricted", "status": "processing"},
                          COMPANY["id"], "restricted", docid)
        service.process_document(ORG, docid)
        if service.store.job(ORG, docid)["state"] != "succeeded":
            raise RuntimeError("document_processing_failed")
    req = AssessmentRequest(policy_id=policy_id, baseline=baseline)
    jid, _ = service.store.create_job(ORG, "assessment", COMPANY["id"], "compliance", req.wire(), str(uuid.uuid4()))
    service.run_assessment(ORG, jid)
    job = service.store.job(ORG, jid)
    # Explicitly exercise the closed-data egress guard, including in baseline mode.
    # This probe is reported separately, not included in the latency/call savings comparison.
    if case == "secret_injection":
        probe_id = str(uuid.uuid4())
        before = len(getattr(service.providers["jev"], "calls", []))
        service.gateway(ORG, probe_id).decide(Evidence(id="private-probe", content=SECRET_DOCUMENT,
                                                   classification="restricted"), COMPANY)
        probe = service.store.audits(ORG, probe_id)
        blocked = any(e.get("operation") == "egress" and e.get("status") == "blocked" for e in probe)
        if service.config.gate == "jev" and not blocked:
            raise RuntimeError("egress_probe_failed")
        if job["result"]:
            job["result"]["privateProbe"] = {"blocked": blocked, "audit": probe}
        if getattr(service.providers["jev"], "mode", "live") == "fixture":
            assert len(service.providers["jev"].calls) == before
    return job


def run(mode, gate, preflight_only=False, root=None):
    config = Settings(gate=gate, data_dir=Path(root) if root else Path(tempfile.mkdtemp(prefix="palladion-control-demo-")))
    ps = fixture_providers() if mode == "fixture" else providers(config)
    status = [p.status() for p in ps.values()]
    report = {"mode": mode, "data": "fictional", "providers": status, "cases": [],
              "notice": "Fixture timings/decisions are not model benchmarks. Energy savings are not measured."}
    required = {"qwen", "openjev"} | ({"jev"} if gate == "jev" else set())
    ready = mode == "fixture" or all(p["status"] == "available" for p in status if p["provider"] in required)
    report["ready"] = ready
    if preflight_only or not ready:
        return report, 0 if ready else 2
    success = True
    for case in CASES:
        pair = {}
        for baseline in (True, False):
            case_root = config.data_dir / (case + ("-baseline" if baseline else "-gated"))
            service = Service(config, Store(case_root), ps, FixtureSource(case))
            try:
                job = run_case(service, case, baseline)
                result = job["result"]
                pair["baseline" if baseline else "gated"] = {
                    "state": job["state"], "error": job["error"],
                    "riskScore": result["riskScore"] if result else None,
                    "classification": result["classification"] if result else None,
                    "policyStatus": result["policyReview"]["status"] if result else None,
                    "events": [e["eventKey"] for e in result["events"]] if result else [],
                    "metrics": result["metrics"] if result else None,
                    "durationMs": result["durationMs"] if result else None,
                    "privateProbe": result.get("privateProbe") if result else None,
                }
                success &= job["state"] == "succeeded"
            except Exception:
                pair["baseline" if baseline else "gated"] = {"state": "failed", "error": "demo_case_failed"}
                success = False
        expected = {"kestrel-deal"} if case in {"namesake", "deal"} else {"kestrel-breach"}
        gated_events = set(pair["gated"].get("events", []))
        pair["missedMaterialEvents"] = sorted(expected - gated_events)
        pair["case"] = case
        pair["passed"] = (pair["gated"]["state"] == "succeeded" and pair["baseline"]["state"] == "succeeded"
                          and not pair["missedMaterialEvents"])
        if case == "conditional":
            pair["passed"] &= pair["gated"].get("policyStatus") == "conditional_path_proposed"
        if case == "remediation":
            pair["passed"] &= pair["gated"].get("policyStatus") == "remediation_required"
        if case == "secret_injection":
            pair["passed"] &= pair["gated"].get("classification") == "restricted"
        success &= pair["passed"]
        report["cases"].append(pair)
    report["passed"] = bool(success)
    return report, 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fixture", "live"), required=True)
    parser.add_argument("--gate", choices=("jev", "openjev"), default="jev")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    report, code = run(args.mode, args.gate, args.preflight, args.data_dir)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n")
        args.output.chmod(0o600)
    print(output)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
