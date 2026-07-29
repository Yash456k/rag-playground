# RAG Evaluation V2 — Build Journal

Append-only engineering journal for the portfolio RAG evaluation rebuild and encoder benchmark.

## 2026-07-29 14:23 IST — Started

- Created branch `eval-v2` from clean `main` at `2c28675`.
- Confirmed the existing evaluation already separates retrieval and live-answer checks and records JSON/JSONL artifacts.
- Confirmed the live containers are running: API and PostgreSQL are healthy; Caddy is up.
- Baseline health probe to `/healthz` returned HTTP 404. This is an endpoint mismatch, not a service outage; the correct application health route still needs to be identified.
- Scope accepted: build basic deterministic evals first, add intermediate diagnostics, verify the harness, then benchmark all six configured embedders with measured timings and produce a readable report.
- Important existing limitations to correct: only 21 answerable retrieval cases, pooled dev/held-out gates, intent overlap between training and held-out cases, binary relevance only, and regex-heavy answer scoring.

## 2026-07-29 14:25 IST — Baseline service check corrected

- Located the real health endpoint in `app/main.py`: `/v1/health`.
- Re-ran the probe successfully. The API reports `status=ok`, all six expected embedders loaded, and complete vector coverage for all 22 currently indexed chunks.
- Resolution to the earlier 404: corrected the probe path; no service or container change was needed.

## 2026-07-29 14:28 IST — Corpus and local-runtime inspection

- Read all three production corpus documents and confirmed the current deterministic chunking produces 22 chunks: 6 experience, 6 projects, and 10 RAG case-study chunks.
- Local system Python could not import `psycopg`, so it could not reuse `app.ingest` directly. Avoided a global install by running the current source read-only inside the existing API image, which already has the pinned dependencies.
- The first `docker run` produced no output because stdin was not attached. Re-ran it with `-i`; the full 22-chunk map was produced successfully.
- No production data or running service was changed.

## 2026-07-29 14:31 IST — Implementation contract

- Chose to extend the existing deterministic Python evaluator rather than replace it with a framework-dependent black box.
- The new suite will have two explicit difficulty tiers (`basic` and `intermediate`), intent-family grouping, development versus challenge splits, graded qrels, required facts, hard negatives, unanswerable cases, family/category slices, ranking metrics, score-threshold diagnostics, uncertainty, and measured latency.
- Target dataset: 40 portfolio-specific intent families with three variants each (120 cases), all grounded in the current 22-chunk corpus. Every variant in a family must stay in the same split.
- Existing evaluation files remain intact as the historical regression suite.
- Codex CLI availability and ChatGPT authentication were verified. It will implement against the `eval-v2` branch under a strict brief; I will inspect the resulting diff and run the real tests and benchmark independently.

## 2026-07-29 14:33 IST — Implementation started

- Launched Codex CLI against the repository with workspace-only write access and a 30-minute bound.
- The brief forbids deployment, database mutation, global installs, network APIs, commits, and edits to this journal.
- Required verification is containerized against the existing pinned API image; the expensive six-model benchmark is reserved for the parent run after review.

## 2026-07-29 14:36 IST — Execution host corrected

- Yash explicitly confirmed that the entire build and benchmark must run on the old laptop.
- The initial Codex process on Hermes was killed immediately. It had not changed source code; only this journal and a temporary branch existed.
- Hermes was restored to clean `main`; the temporary branch and untracked journal there were removed. Production containers and database were never changed.
- Verified the old laptop is online, fully charged, and has 6.6 GiB available RAM, 4 GiB swap, 370 GiB free disk, and a GTX 1650 Ti with 4 GiB VRAM.
- Cloned `Yash456k/rag-playground` to `/home/yash456k/rag-playground` on the old laptop and created the `eval-v2` branch there.
- This journal was moved into the old-laptop checkout. All implementation, validation, model downloads, and benchmarks continue only there.

## 2026-07-29 14:40 IST — Old-laptop toolchain setup

- The old laptop has no Docker, `uv`, Node, or Codex CLI. Chose not to install unrelated system-wide tooling.
- Started an isolated Python environment at `/home/yash456k/rag-playground/.venv-eval` using the repository's pinned development requirements.
- Hermes's already-authenticated Codex is used only to draft source changes against a temporary SSH mirror of the old-laptop checkout. Drafts are synced back before any validation; the authoritative branch, virtual environment, model artifacts, tests, GPU runs, and result files remain on the old laptop.
- The first mirror command failed because the requested local working directory did not exist before command startup. Re-ran from `/home/yash`, created the temporary directory first, and completed the mirror successfully.

## 2026-07-29 14:44 IST — Tuned-model artifacts transferred

- Copied the two existing portfolio-tuned SentenceTransformer artifacts from the production checkout to the old laptop: Portfolio E5 Small and Portfolio GTE Small.
- Transfer size: 257 MiB. No secrets or database data were copied.
- Verified both `model.safetensors` files by SHA-256 on source and destination; both pairs match exactly.
- General Hugging Face models will use their pinned repository revisions from `config/pipeline.yaml` and download into the old laptop's local cache during benchmarking.

## 2026-07-29 14:58 IST — Old-laptop baseline verified

- The isolated `.venv-eval` installation completed successfully with the repository's pinned runtime and development requirements.
- Verified `torch 2.7.1+cu126`, CUDA runtime 12.6, SentenceTransformers 5.1.0, Transformers 4.56.1, and a visible NVIDIA GeForce GTX 1650 Ti Max-Q at compute capability 7.5.
- Ran the unchanged repository baseline before syncing Eval V2: **73 tests passed in 6.82 seconds** (8.81 seconds wall through `/usr/bin/time`, maximum process RSS 810,428 KiB).
- Ran Ruff across the unchanged checkout, excluding only the virtual environment, model artifacts, and generated results: **all checks passed**.
- This gives a clean old-laptop baseline against which Eval V2 changes can be judged.

## 2026-07-29 15:00 IST — Eval V2 implementation and review

- Added a database-free, exact-cosine retrieval evaluator that rebuilds the same 22 production chunks in memory and loads one embedder at a time. This keeps the old laptop within its 7.6 GiB RAM and 4 GiB VRAM limits.
- Added a versioned fact map with 29 atomic claims and exact evidence anchors, 40 intent families, three materially different variants per family, and 120 total cases: 84 development / 36 locked challenge and 60 basic / 60 intermediate.
- Intermediate coverage includes paraphrase, typos/noise, multi-evidence synthesis, history-aware follow-ups, hard-negative contrast, underspecification, false premises, partial answerability, out-of-corpus questions, and prompt injection.
- Added graded qrels (required grade 3, useful support grades 1/2), MRR, hit/precision/required-recall/all-required at K, nDCG, hard-negative hit rate, family consistency, category/difficulty slices, family-cluster bootstrap intervals, answerability threshold diagnostics, and paired per-query comparisons.
- Added sequential benchmark instrumentation for pinned model revision, effective dtype, cold load plus warm-up, corpus indexing, embedding/retrieval/end-to-end latency, throughput, current RSS snapshots, and peak allocated/reserved CUDA memory.
- The benchmark mirrors production history rewriting and production's candidate-diversity pass after exact cosine ranking.

### Review roadblocks and fixes

- Initial generated qrels used only grade 3, so nDCG was not genuinely graded. Added human-reviewed supporting chunks at grades 1/2 and strict qrel/evidence validation. Removed several merely adjacent but not actually useful supporting labels.
- The first benchmark draft included assistant history and raw top-K ranking, which differed from production. Changed it to prior user messages only and exact production query formatting, then reproduced the 12-candidate diversity selection.
- Unanswerable cases were initially averaged as zero-valued retrieval failures. Changed relevance metrics and confidence intervals to answerable cases only; answerability/refusal behavior remains in fixed-threshold diagnostics.
- The challenge threshold was initially optimized on challenge scores. Changed threshold calibration to development data only and applied that fixed threshold to challenge; challenge-only runs now say calibration is unavailable rather than leaking.
- Paired comparisons initially included a pooled dev+challenge view without enough warning. Comparisons are now split by dev/challenge and tier; the pooled view is explicitly informational only.
- Existing encoder training covers almost every direct corpus fact, so a pristine fact-family holdout cannot honestly be created without new untuned corpus facts. The locked challenge is now explicitly labeled as query-form, compositional, answerability, and adversarial generalization. Every case records its training-overlap status and generalization axis.
- A code-drafting change made production ingestion imports lazy only to accommodate the lightweight mirror. Reverted that production modification; the old laptop's proper runtime has all dependencies and Eval V2 now consumes the unchanged production chunker.

## 2026-07-29 15:07 IST — Validation failures resolved

- First full old-laptop run after syncing Eval V2: **91 passed, 1 failed**. The failure was in the new model-failure-isolation test because its fake timing payload omitted the newly added RSS fields; the production benchmark itself had generated a valid smoke result. Updated the fixture to match the real schema.
- First Ruff run found 10 issues: import ordering, intentional deterministic `random.Random` flagged as security randomness, the script's deliberate repository-path bootstrap flagged as E402, and one test style warning. Fixed all without suppressing functional checks.
- Regenerated the datasets and challenge lock on the old laptop after tightening the relevance labels.
- Final full old-laptop run: **92 tests passed in 9.02 seconds** (10.93 seconds wall; maximum process RSS 796,144 KiB).
- Final Ruff and `git diff --check`: **all checks passed**.
- Dataset validation reports 29 claims, 120 cases, 40 families, 22 exact production chunks, 102 answerable / 18 unanswerable cases, and 111 grade-3, 57 grade-1, and 27 grade-2 qrel assignments across variants.

## 2026-07-29 15:11 IST — Model preparation and real smoke run

- Downloaded all four general embedders at the exact revisions pinned in `config/pipeline.yaml`; the two tuned artifacts were already checksum-verified locally. Download wall time was 443.95 seconds, with a 1,432,296 KiB maximum process RSS. Network download time is recorded separately and excluded from inference comparisons.
- Ran a real CUDA smoke benchmark with Portfolio GTE Small on 45 basic development queries. It completed successfully, produced raw JSONL plus summary/environment/report artifacts, and used 199.2 MiB peak allocated / 246.0 MiB peak reserved CUDA memory.
- The first smoke exposed a Transformers deprecation warning for `torch_dtype`. Updated model loading to the current `dtype` argument and reran the smoke successfully with no warning.
- Warm-cache rerun wall time was 7.93 seconds with 1,254,300 KiB maximum process RSS. The suite is now ready for the controlled six-model run.

## 2026-07-29 15:25 IST — Six-model benchmark and recommendation

- Reverified the execution host immediately before the full run: `yash456k-GF63-Thin-9SCSR`, battery 100% Full, GTX 1650 Ti Max-Q idle with 0 MiB allocated, and 6.5 GiB host RAM available.
- The first benchmark command failed before any model loaded because `--embedder all` was interpreted as a literal unknown model ID. The CLI selects every model when the option is omitted. Removed the invalid option and restarted; the failed attempt took 4.40 seconds and did not contaminate model timings.
- The corrected old-laptop run loaded and evaluated all six pinned routes successfully. It completed in 79.17 seconds with 3,556,272 KiB maximum process RSS. There were no model failures and the benchmark log was empty.
- MiniLM produced the best quality/speed balance: development/challenge nDCG@5 0.824/0.784, development/challenge required Recall@5 0.938/0.950, 4.486 ms mean end-to-end latency, 222.4 queries/s, and 157.8 MiB peak allocated CUDA memory.
- Current Portfolio GTE produced development/challenge nDCG@5 0.784/0.768 and Recall@5 0.917/0.933 at 7.699 ms mean latency and 198.8 MiB peak allocated CUDA memory. MiniLM was 1.72x faster with nDCG@5 deltas of +0.040 development and +0.016 challenge, but uncertainty intervals overlap.
- BGE Base reached perfect challenge Recall@5 and 0.780 challenge nDCG@5 at 7.733 ms, using 549.5 MiB allocated CUDA memory. Qwen3 used 1,596.6 MiB and averaged 98.145 ms without winning quality, so it is not practical for this corpus/runtime.
- Configured similarity thresholds are too permissive for intermediate unanswerable cases. Portfolio GTE's configured threshold produced false-answer rates of 0.917 on development and 0.667 on challenge. Development calibration improves rejection but transfers with substantial false refusals, so no threshold was changed.
- Hard-negative separation remains weak even for the strongest models and is a higher-value next training target than blindly increasing model size.
- An independent review agent timed out before returning a final review. Its partial transcript covered an earlier draft and flagged the then-ungraded qrels and training overlap; both were already resolved or explicitly documented before the committed benchmark. Acceptance is based on the old-laptop 92-test suite, Ruff, strict data validation, smoke run, and successful six-model execution—not on the timed-out agent.
- Final decision: keep Portfolio GTE as production default for now. MiniLM is the leading promotion candidate, pending a fresh locked challenge set because the current challenge is now inspected and its model differences are modest.
- Added polished `evaluation/EVAL_V2_REPORT.md` and machine-readable `evaluation/EVAL_V2_RESULTS.csv`. Raw artifacts remain under ignored `evaluation/results/v2-full/` on the old laptop.

## 2026-07-29 15:29 IST — Default-embedder correction

- Rechecked the live production `/v1/config` endpoint and current source after the report draft. The actual live default is `bge-small`, derived positionally from `embedders[1]`; Portfolio GTE is configured and selectable but is not the default.
- The preceding draft note calling Portfolio GTE the current default was incorrect. The polished report was corrected before commit.
- Against the real BGE Small default, MiniLM improved development/challenge nDCG@5 by +0.136/+0.112 and Recall@5 by +0.125/+0.083 while cutting mean latency by 41.3% and peak allocated VRAM by 20.6%.
- Recommendation corrected accordingly: MiniLM has enough measured advantage to replace BGE Small in a controlled follow-up. This evaluation branch still makes no production-default or deployment change. A separate explicit `default_embedder` configuration field is preferable to the current positional choice.

## 2026-07-29 18:25 IST — Expanded embedder search and benchmark harness

- Searched current first-party Hugging Face model cards and API metadata for compact retrieval encoders suitable for the old laptop's 4 GiB GTX 1650 Ti and approximately 7.6 GiB RAM. Selection emphasized retrieval-ready models at or below roughly 600M parameters, immutable revisions, documented prompt behavior, compatible embedding dimensions, and explicit licenses.
- Added 11 benchmark-only challengers: GTE ModernBERT Base, Mixedbread Embed Large V1, Snowflake Arctic Embed M V2, Nomic Embed Text V2 MoE, LFM2.5 Embedding 350M, EmbeddingGemma 300M, Microsoft Harrier OSS 270M, Perplexity Embed V1 0.6B, BGE M3, Stella EN 400M V5, and Jina V5 Nano Retrieval.
- Each candidate is pinned by a 40-character repository revision in `evaluation/v2/challengers.yaml`. The manifest also records dimensions, native-safe dtype, query/document prompt names, remote-code requirements, parameter count, license, source URL, and selection rationale.
- The challenger manifest extends only the evaluator. It does not change `config/pipeline.yaml`, database vector columns, the API, or the live `bge-small` default.
- Enhanced the benchmark loader to honor SentenceTransformers prompt names rather than naively concatenating instructions where prompt-exclusion pooling matters, and to enable remote code only for candidates whose first-party repository requires it.
- Benchmark-only models have no production similarity threshold. Reports now mark configured-threshold diagnostics unavailable instead of inventing a threshold, while preserving development-only calibration analysis.
- Added focused tests for manifest integrity, production-ID separation, prompt/prefix exclusivity, prompt forwarding, missing configured thresholds, and CLI challenger selection. Old-laptop focused validation passed: **23 tests passed in 6.33 seconds**; Ruff and `git diff --check` passed after two line-length-only fixes.
- Jina V5 Nano is included as an explicit compatibility/licensing probe, not a deployment recommendation: its card requires a newer runtime than the pinned environment and its CC-BY-NC-4.0 license is non-commercial. EmbeddingGemma is similarly probed despite its manual license gate. Any failure remains model-specific and will not abort other candidates.
