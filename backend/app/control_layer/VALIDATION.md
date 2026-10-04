# Validation record — 2026-10-04

Implementation branch: `pofa`. Base commit: `9ccbada`. Checks below distinguish deterministic application tests from actual model inference. Target deployment requested by the team: M4 Pro / 48 GB. The execution host available for these checks reported Apple M4 / 16 GB.

| Check | Actual result | Meaning |
|---|---|---|
| `make control-test`, isolated locked Python 3.13 environment | **67 passed** | Real SQLite, FastAPI handlers, role checks and provider HTTP transports; model answers explicitly doubled; sockets disabled |
| `make control-demo` | **5/5 fictional cases passed** | Baseline vs gated workflow, both policy outcomes, dedupe, local private document and blocked egress probe |
| Standalone API process | **Passed** | `/health` 200, OpenAPI exposes 13 control paths, protected endpoint without JWT 401 |
| Pinned upstream OpenJev installation | **Passed** | `GPT-AGI/OpenJev@0e7bb990211df139da13dc67aa2a7aceca311af7`, separate locked environment |
| Actual OpenJev inference | **Transport/schema passed; privacy semantic smoke failed** | Real `Qwen/Qwen2.5-0.5B-Instruct` weights, MPS, native chat template, no text generation |
| Actual OpenJev HTTP sidecar | **Passed** | `/v1/models` and `/v1/systemone` returned 200; response schema checked |
| Qwen3.8-27B live inference | **Not run** | No Qwen endpoint or MLX checkpoint path configured on the available host |
| Jev API live inference | **Not run** | `TYPESAFE_API_KEY` absent; no paid call made |
| Live end-to-end company assessment | **Not run** | Requires Qwen; cloud-gated version additionally requires Jev access |
| New Supabase mutations/migrations | **None** | Bridge tests enforce select/filter-only access; local data store is separate |
| `git diff --check` | **Passed** | No whitespace errors |

## Evidence files

- [Fixture report](evidence/fixture-report.json): explicitly synthetic, both paths for all five cases. No invented usage/cost figures.
- [Live preflight](evidence/live-preflight.json): captured while the OpenJev sidecar was running; Qwen unavailable, OpenJev available, Jev not configured. This is a point-in-time readiness snapshot.
- [OpenJev direct smoke](evidence/openjev-live-smoke.json): actual probability distributions, device and timing for two synthetic inputs.
- [OpenJev HTTP smoke](evidence/openjev-http-smoke.json): actual sidecar response and status codes.
- [Repeatable OpenJev privacy smoke](evidence/openjev-privacy-smoke.json): expected binary labels and explicit failed semantic outcome; reproduce with `python -m app.control_layer.smoke` while the sidecar runs.
- [Legacy comparison](evidence/legacy-comparison.json): failing test IDs compared against a temporary archive of the unchanged base commit; no branch switch.

## OpenJev quality finding

On the neutral sentence “A kestrel is a bird of prey.” the real scorer selected `birds` with probability approximately 0.993, but assigned approximately **0.679** to the question asking whether the sentence contains a private credential. On an explicit synthetic API-key string, that privacy probability was approximately **0.706**. This is a false-positive privacy result on the neutral sentence and insufficient separation between these two inputs. It is **not** evidence of a calibrated privacy classifier.

The native instruct chat template is used in the final implementation. It did not remove this limitation in the smoke test. Consequently local OpenJev relevance negatives remain advisory, and uncertain privacy results keep material local. On some workloads this will increase local Qwen work and reduce the usefulness of the cloud gate. Measure on representative labeled data before claiming token/cost savings or relaxing any thresholds. No thresholds were loosened to make the smoke test look successful.

An additional direct scoring probe with literal single-token `yes`/`no` answers instead of option letters returned P(yes) approximately 0.223 for the neutral sentence and 0.469 for the synthetic credential. That alternative would miss the credential at a 0.5 cutoff; it was not adopted. Prompt formatting alone did not establish a reliable privacy classifier.

Cached model load took about 4.1 seconds in this one process. The first two-question inference took about 879 ms; the next about 195 ms. The separate HTTP single-question smoke recorded about 521 ms. Different warm-up states and tiny sample size make these **smoke timings, not a throughput benchmark**. Initial weight download was much slower; Xet stalled and ordinary HTTP download succeeded with `HF_HUB_DISABLE_XET=1`.

## Existing repository suite

Command from the repository root: `(cd backend && .venv/bin/python -m pytest tests -m 'not db and not live' -q)`.

The existing tests produced **468 passed, 75 failed, 10 errors, 2 skipped, 2 xfailed**, with 57 DB/live tests deselected. Failures include old tests that still expect unimplemented 501 routes and a `not_implemented` stub, plus existing configuration/contract mismatches.

The same failing test IDs were reproduced against an archive of base commit `9ccbada`: **zero newly failing test IDs** in the implementation checkout. The archive additionally fails the test that asks Git whether a secrets file is ignored, because an archive has no `.git` directory; that archive-only result is recorded separately. This comparison does not claim the entire repository is green. The new module's isolated suite is green.

## Remaining live acceptance

On the team's trusted M4 Pro / 48 GB host, configure the actual Qwen3.8-27B 4-bit checkpoint/server and TypeSafe key, run `make control-preflight`, then run the CLI with `--mode live` for each gate. Preserve those reports separately. Real Qwen output quality, Jev filtering recall, net cost savings and end-to-end latency remain unverified until those calls succeed and their evidence is reviewed.

Fixture success, HTTP readiness, evidence-quotation matching and output-schema validation do not establish factual correctness, calibrated risk scores or legal/compliance suitability.
