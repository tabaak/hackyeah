# Palladion Local AI Control Layer

A local, inspectable decision gateway for reputation and client-risk analysis. Public material can go through Jev; private documents and policy stay on the trusted local host. A high risk score triggers policy review and human-reviewed remediation, never automatic client acceptance or rejection.

## Judge quick start

From the repository root, with [uv](https://docs.astral.sh/uv/) installed:

```sh
make control-demo
make control-test
```

`control-demo` creates an isolated Python 3.13 environment from a pinned dependency lock and executes five **fictional** cases without keys, model downloads, Supabase, Docker or the frontend. The first installation requires package-network access. Subsequent fixture inference is offline. `control-test` blocks socket connections and tests real SQLite persistence and HTTP handlers with explicit provider doubles.

Every report says `mode: fixture` or `mode: live`. Fixture answers are deterministic Python test doubles, **not** Qwen/Jev accuracy or latency measurements. The production HTTP application never selects them.

Five cases: namesake/noise; a public supply deal; high risk with a permitted conditional route; high risk without an exception; a restricted document containing a synthetic credential and prompt injection. Both baseline and gated paths run on the same corpus. The report includes missed expected material events, inference call counts, usage completeness and an explicit private-egress probe. All names, policies, reports and secrets in these fixtures are invented.

## What is implemented

```text
Existing public company/feed records (read-only, organization-scoped)
                │
         dedupe + local privacy checks
                │
     Jev API or local OpenJev typed decisions
                │ material / uncertain
          local Qwen3.8-27B
                │
 events + claim evidence + 0–10 risk + policy review
                │
    local SQLite, files, FTS and audit records
```

- `gateway.py`: the only inference gateway used by this module; unknown/closed data cannot use Jev. Legacy `LLM_FORCE` is ignored.
- `providers.py`: bounded HTTP timeouts, strict Noul/Choice validation, Qwen JSON/model validation, no redirect or proxy forwarding, generic errors without prompt content.
- `store.py`: organization-scoped SQLite/FTS, idempotent jobs, private files, audit records and restart recovery.
- `service.py`: full-fragment document scans, evidence validation, dedupe, risk and activated-policy interpretation.
- `api.py`: separate authenticated API, one worker, loopback port 8002. Supabase is read-only for company/feed data and used for existing JWT verification; private case data is not uploaded.
- `openjev_server.py`: small local wrapper around the pinned upstream HF scorer with validated, unique single-token labels. It does not claim Jev-equivalent quality.

This module is **separate from the legacy app on port 8000**. That app still has its original Supabase document uploads and LLM routes. Upload private material only to `/api/v1/control/companies/{id}/documents` on the trusted local service. Starting this module does not migrate or erase documents already uploaded through the old application.

## Live setup on the M4 Pro / 48 GB host

Keep the API, files, SQLite and both model servers on the same trusted host. All local model URLs are restricted to loopback. A workstation elsewhere on the LAN is not silently treated as local.

1. Run `make control-setup`. Export the settings documented in `backend/.env.control.example`. `TYPESAFE_API_KEY` is needed only for cloud Jev. Existing Supabase JWT configuration is needed only for the HTTP API/source bridge; the synthetic CLI has no database dependency.
2. Start your installed **Qwen3.8-27B MLX 4-bit** server on `127.0.0.1:8001` with an OpenAI-compatible `/v1/chat/completions` and `/v1/models`. Set `CONTROL_QWEN_MODEL` to its exact served ID and `CONTROL_QWEN_PATH` to its local MLX checkpoint directory. Preflight checks 4-bit configuration and weight-file presence, records the config hash, and checks the served ID. These checks do not cryptographically attest that the server loaded those weights. The ID must identify Qwen3.8-27B; a different model or an unavailable checkpoint is not replaced silently. Model installation and the MLX serving environment are separate from the control API environment.
3. Install and run local OpenJev:

   ```sh
   make control-openjev-setup
   make control-openjev
   ```

   This uses its own Python environment and `Qwen/Qwen2.5-0.5B-Instruct`. First loading downloads the model to the normal Hugging Face cache. Once cached, run with `HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1`. OpenJev produces scores, not generated prose. Do not treat its entropy-based confidence as calibrated probability of correctness.
4. In another terminal, with the same configuration:

   ```sh
   export CONTROL_GATE=openjev
   make control-preflight
   make control-api
   ```

   For public-cloud filtering set `CONTROL_GATE=jev` and configure the TypeSafe key. Both local services remain required because public-cloud routing first runs a local privacy check.

API documentation: <http://127.0.0.1:8002/docs>. `/health` verifies the API process only. `/api/v1/control/providers/status` checks configured models separately. A successful health response is not a model-readiness claim. Use one API worker; a filesystem lock prevents concurrent processes from recovering each other's jobs.

Run real models against the fictional corpus:

```sh
cd backend
.control-venv/bin/python -m app.control_layer.demo --mode live --gate openjev --output .control-data/live-report.json
# With TypeSafe access, compare the cloud public gate as well:
.control-venv/bin/python -m app.control_layer.demo --mode live --gate jev --output .control-data/jev-live-report.json
```

An unavailable required model causes exit 2 and a readiness report, not a fixture fallback. Individual case failures cause exit 1. See [VALIDATION.md](VALIDATION.md) for actual results from this implementation environment.

To reproduce the isolated real OpenJev privacy smoke while its sidecar is running:

```sh
cd backend
.control-venv/bin/python -m app.control_layer.smoke
```

This checks two synthetic inputs only. Exit 1 explicitly records a semantic privacy-smoke failure; exit 2 means transport/contract failure. The initial small model fails the neutral privacy example, as documented in the validation record. A passing smoke would still not establish production quality.

## API workflow

All `/api/v1/control` routes require the existing Supabase bearer JWT. Organization and role come from verified claims, never a body parameter. Responses use camelCase. Policy creation/activation requires compliance. Restricted evidence and all results derived from it require compliance, including audit and sector aggregation.

| Method | Path after `/api/v1/control` | Result |
|---|---|---|
| GET | `/providers/status` | Actual provider/model readiness, no keys |
| POST | `/companies/{id}/documents` | Multipart `file`, `classification`; local processing job |
| POST | `/policies` | `{name,text,classification}`; local draft job |
| GET | `/policies/{id}` | Source and proposed structure for compliance review |
| POST | `/policies/{id}/activate` | Reviewed `{clauses:[...]}`; immutable activated version |
| POST | `/companies/{id}/assessments` | `{purpose,days,policyId,baseline}`; assessment job |
| GET | `/jobs/{id}` | Processing state/result for documents, policies or assessments |
| GET | `/assessments/{id}` | Events, claims, risk, policy review, coverage and metrics |
| GET | `/assessments/{id}/audit` | Local routing/usage record without prompts |
| GET | `/companies?sector=...` | Locally tracked companies, optional sector filter |
| PUT | `/companies/{id}/sector` | Local `{sector}` override; no Supabase schema changes |
| GET | `/sectors` | Expanded sector dictionary |
| GET | `/sectors/summary?sector=...` | Distribution within the locally tracked sample |

The three job-creation routes require `Idempotency-Key`. Reusing it with the same request returns the same job, including a failed job; a different request with the same key returns 409. Jobs persist as `queued/running/succeeded/failed`. Pending jobs at startup become `failed` with `interrupted`; they are not silently charged/replayed. A new key deliberately creates a new attempt.

Example assessment (use your existing company ID and token; this example does not create remote records):

```sh
curl -sS http://127.0.0.1:8002/api/v1/control/companies/COMPANY_ID/assessments \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: review-001' \
  --data '{"purpose":"onboarding","days":60,"policyId":"ACTIVATED_POLICY_ID"}'
```

For a crisis, use `purpose: crisis`; events with known event dates within 72 hours are highlighted. An article publication date does not prove when its underlying incident occurred. Default assessment window is 60 days. Import is capped at 100 recent mentions; cap, failed interpretation and omitted evidence cause an insufficient-evidence score.

Policy source is stored with its hash; each upload creates a distinct version ID. Qwen proposes structured clauses. Compliance must inspect the original source and every proposed clause/exception, then submit the reviewed structure to `/activate`. Exact-substring validation prevents invented quotations but **does not prove an extracted rule is a faithful interpretation**; that is the reviewer's responsibility. Activated rules are immutable. New wording requires a new policy upload/ID.

The policy engine preserves applicable prohibitions even if the model omits them. Proposed conditions/remediation are copied from activated rules, not unconstrained model recommendations. Recommendations never decrease the original risk score before changes are verified. There is no endpoint that automatically accepts or rejects a customer.

## Data handling and assessment limits

- Uploaded files start at least `internal`, even if marked public. Qwen inspects every extracted fragment; whole-document classification is the maximum of supplied and detected levels. There is no automatic declassification. PDF/TXT limit: 5 MiB, 60,000 extracted characters. Image-only PDFs fail explicitly; OCR is not included.
- Private artifacts are under `CONTROL_DATA_DIR` (default `.control-data` relative to the backend working directory), excluded from Git. Directory permissions are 0700; files/SQLite are 0600. They are **not application-encrypted**: protect the host and use disk encryption. SQL/FTS and local model processing are inside the same trusted boundary.
- Public provenance alone does not permit a Jev request: local pattern checks and an OpenJev privacy decision run first. Failed or uncertain checks keep content local. These detectors are conservative heuristics/models, not a proof that arbitrary personal data can never be missed. Explicit non-public labels and private-origin documents always override model decisions.
- OpenJev's relevance answers are advisory: it cannot automatically discard material in this version. Cloud Jev can skip only when both entity and material-event scores are at most 0.05 and there are no independent alarm words. These thresholds are not a calibrated accuracy guarantee.
- Exact quotes and known evidence IDs are validated. Primary allegations still need to be distinguished from established wrongdoing. News publisher allowlisting indicates source independence, not factual truth. Company statements alone cannot verify claims or justify a numerical score.
- Duplicate exact text and repeated extracted event IDs collapse. Semantic dedupe remains model-dependent; the risk model is instructed not to add risk for syndicated copies. No statistical risk calibration is claimed.
- Logs/audit contain timestamp, route, model, decision, fixed reason codes and usage; they do not contain prompts, response bodies or detected secret values. The authenticated assessment result does contain its supporting evidence, under the inherited access classification.
- Private documents are not reachable by legacy response drafting, cloud push notifications, external embeddings or automatic publishing.

## Measurements

Baseline processes every deduplicated article through Qwen; gated mode applies the same preparation, then Jev/OpenJev. Compare both on the same corpus and provider configuration. Assessment metrics include privacy/relevance gates, failed attempts, extraction, risk synthesis and policy matching. Document scanning and policy preparation are outside that assessment timing and must be considered when estimating whole-system costs. The explicit private-egress test probe is reported separately.

Usage is read from providers; missing usage stays null with `usageComplete: false`. Fixture providers intentionally supply no fictional token counts. Optional `CONTROL_PRICING_JSON` supplies your actual USD-per-million input/output rates for each used provider, e.g. keys `jev`, `qwen`, `openjev`, each with `inputPerMillion` and `outputPerMillion`. Total cost remains `unknown` unless every call has usage and a configured rate. Zero is only meaningful if explicitly configured; local compute is not assumed free.

The CLI retains wall-clock times and missed expected fixture events; these are not population-level recall estimates. Model warm-up, hardware and quantization affect live timings. Energy/datacenter savings are not measured and must not be presented as demonstrated results.

## Sources and third-party code

- [TypeSafe HTTP API](https://docs.typesafe.ai/api): official typed questions; commercial Jev access requires your own account.
- [Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B): model identity and upstream model terms.
- [GPT-AGI/OpenJev pinned source](https://github.com/GPT-AGI/OpenJev/tree/0e7bb990211df139da13dc67aa2a7aceca311af7): independent MIT-licensed interface-pattern implementation. Its HTTP serving and MLX roadmap are not assumed implemented; our wrapper uses its actual HF scoring primitive. No claim of TypeSafe affiliation, training equivalence or matching accuracy.
- [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct): Apache-2.0 model used by the optional scorer. Weights are downloaded separately, not committed.

`requirements-control.txt` and `requirements-control-openjev.txt` lock dependency versions; `.in` files record direct requirements. Runtime dependency/license metadata is available through `python -m pip show PACKAGE` or Python `importlib.metadata`. Existing repository licensing remains unchanged; this module does not relicense upstream code or weights.
