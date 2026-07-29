# Portfolio RAG Eval V2 — Benchmark Report

**Run:** 2026-07-29 15:20:48 IST
**Host:** `yash456k-GF63-Thin-9SCSR` (old laptop)
**GPU:** NVIDIA GTX 1650 Ti Max-Q, 4 GiB
**Code:** `eval-v2` at `faa04bb58f79ef0b08a9234ed8f5044abe710e4d`
**Result hash:** `summary.json` SHA-256 `d9b5edd125262ae673316fb007802590919484d6065ee4e886e78d02154d147f`

## Decision

The live API currently returns **`bge-small` as the default embedder**. The benchmark supports replacing it with **`minilm-l6` in a controlled production change**, but this evaluation branch does not alter or deploy that default.

Compared with the current BGE Small default, MiniLM:

- Improved development nDCG@5 by **+0.136** and challenge nDCG@5 by **+0.112**.
- Improved development Recall@5 by **+0.125** and challenge Recall@5 by **+0.083**.
- Won/tied/lost paired nDCG@5 queries 30/28/14 on development and 18/7/5 on challenge.
- Averaged 4.49 ms end-to-end versus 7.64 ms: **1.70× faster / 41.3% lower latency**.
- Used 157.8 MiB peak allocated VRAM versus 198.8 MiB: **20.6% less**.

This is a clear practical improvement over the current default, even though the family-bootstrap intervals still overlap. MiniLM should be the next production default candidate; threshold behavior must be handled separately.

Portfolio GTE remains competitive but is not the current live default. MiniLM exceeded it by +0.040 development and +0.016 challenge nDCG@5 while running 1.72× faster. Those smaller differences are not conclusive enough to claim that MiniLM universally dominates the tuned GTE route.

`bge-base` is the recall-oriented alternative. It reached 1.000 challenge Recall@5 and 0.867 Recall@3, but used 549.5 MiB VRAM and did not beat MiniLM on nDCG or speed.

`qwen3-embedding` is not justified here. It used 1,596.6 MiB VRAM, averaged 98.15 ms per query, and was **21.9× slower than MiniLM** without winning the held-out quality comparison.

## Evaluation design

- **Corpus:** the exact 22 chunks produced by the production chunker from the three portfolio documents.
- **Cases:** 120 cases from 40 intent families, three variants per family.
- **Splits:** 84 development / 36 locked challenge.
- **Tiers:** 60 basic / 60 intermediate.
- **Answerability:** 102 answerable / 18 unanswerable.
- **Intermediate cases:** paraphrase, noise/typos, multi-evidence synthesis, history-aware follow-ups, hard negatives, underspecification, false premises, partial answerability, out-of-corpus questions, and prompt injection.
- **Relevance:** grade 3 required evidence; grades 1–2 useful support.
- **Metrics:** nDCG, MRR, hit rate, precision, required evidence recall, all-required success, hard-negative hit rate, family consistency, category/difficulty slices, family-cluster bootstrap intervals, answerability thresholds, and paired per-query W/T/L comparisons.
- **Retrieval path:** pinned model revision, production query/document prefixes, exact normalized cosine, 12 candidates, and the production diversity selector. The first three results therefore represent the current production `top_k: 3`; @5 is the wider diagnostic view.
- **Timing:** three measured runs per query after three warm-ups. Models were loaded sequentially and CUDA memory was released between models. Network downloads were completed before timing.

## Quality at the production depth and at K=5

| Model | Dev nDCG@3 | Dev R@3 | Challenge nDCG@3 | Challenge R@3 | Dev nDCG@5 | Challenge nDCG@5 |
|---|---:|---:|---:|---:|---:|---:|
| **MiniLM L6** | **0.788** | 0.868 | **0.731** | 0.850 | **0.824** | **0.784** |
| Qwen3 0.6B | 0.772 | **0.882** | 0.675 | 0.817 | 0.806 | 0.744 |
| Portfolio GTE Small | 0.745 | 0.840 | 0.722 | 0.850 | 0.784 | 0.768 |
| Portfolio E5 Small | 0.741 | 0.812 | 0.706 | **0.867** | 0.776 | 0.752 |
| BGE Base | 0.728 | 0.792 | 0.726 | **0.867** | 0.760 | 0.780 |
| BGE Small | 0.632 | 0.681 | 0.600 | 0.683 | 0.688 | 0.671 |

### Basic versus intermediate

| Model | Dev basic nDCG@5 | Dev intermediate nDCG@5 | Challenge basic nDCG@5 | Challenge intermediate nDCG@5 |
|---|---:|---:|---:|---:|
| MiniLM L6 | **0.840** | 0.795 | 0.685 | **0.882** |
| BGE Small | 0.734 | 0.610 | 0.536 | 0.806 |
| BGE Base | 0.785 | 0.720 | **0.724** | 0.835 |
| Qwen3 0.6B | 0.812 | **0.796** | 0.687 | 0.801 |
| Portfolio E5 Small | 0.825 | 0.696 | 0.675 | 0.830 |
| Portfolio GTE Small | 0.838 | 0.693 | 0.674 | 0.862 |

MiniLM is the most balanced result. BGE Base is stronger on challenge recall, while Portfolio GTE remains competitive on challenge intermediate queries. No model dominates every slice.

## Speed and resources on the old laptop

| Model | Load + warm-up | Corpus encode | Mean E2E | P95 E2E | Throughput | Peak VRAM allocated/reserved |
|---|---:|---:|---:|---:|---:|---:|
| **MiniLM L6** | 2.439 s | **0.088 s** | **4.486 ms** | **4.552 ms** | **222.4 q/s** | **157.8 / 212.0 MiB** |
| BGE Small | 2.215 s | 0.167 s | 7.639 ms | 7.738 ms | 130.7 q/s | 198.8 / 246.0 MiB |
| BGE Base | 2.104 s | 0.414 s | 7.733 ms | 8.148 ms | 129.1 q/s | 549.5 / 666.0 MiB |
| Qwen3 0.6B | 5.891 s | 7.792 s | 98.145 ms | 108.499 ms | 10.2 q/s | 1,596.6 / 1,664.0 MiB |
| Portfolio E5 Small | **0.393 s** | 0.123 s | 7.667 ms | 7.781 ms | 130.2 q/s | 200.1 / 250.0 MiB |
| Portfolio GTE Small | **0.134 s** | 0.167 s | 7.699 ms | 7.786 ms | 129.7 q/s | 198.8 / 246.0 MiB |

The full six-model process completed in **79.17 seconds** with **3,556,272 KiB maximum process RSS**. The one-time pinned-model download took 443.95 seconds and is excluded from inference timing.

## Main failures

### Answerability thresholds

The configured thresholds are too permissive on intermediate unanswerable questions:

- Portfolio GTE at 0.770: development false-answer rate 0.917; challenge false-answer rate 0.667.
- MiniLM at 0.180: development false-answer rate 1.000; challenge false-answer rate 0.833.
- BGE Small, BGE Base, and Portfolio E5 answered every intermediate unanswerable development case at their configured thresholds.
- Qwen's configured intermediate false-answer rate was 0.917 on development and 1.000 on challenge.

Development-calibrated thresholds reduce false answers but increase false refusals and transfer poorly to challenge. For Portfolio GTE intermediate, 0.819 changed challenge false-answer/false-refusal rates from 0.667/0.000 to 0.333/0.333. Do not ship a new threshold from this small set alone.

### Hard-negative separation

Retrieval often returns the hand-labelled distractor inside the top five. Portfolio GTE's hard-negative hit rate was 0.714 on development and 1.000 on challenge; MiniLM's was 0.619 and 0.889. This should be the next training/evaluation target even when required evidence recall is high.

### Repeated retrieval misses

Failures cluster around:

- AIVID scale/UI wording.
- RAG model/interface/resource details.
- Multi-evidence career and RAG synthesis.
- Lexicalized NSK race-condition queries.
- Partial-answerability cases.

The raw report contains every per-model failure and highest-scoring refusal case.

## Practical recommendation

1. **Promote MiniLM over the current BGE Small default in a controlled follow-up change.** This run demonstrates a large, consistent quality gain plus lower latency and VRAM.
2. **Make the default embedder explicit in configuration.** The current API derives it positionally from `embedders[1]`, which is fragile and obscured the actual live default during reporting.
3. **Create a fresh locked challenge set for later model-selection claims.** Existing training already covers nearly every direct corpus fact, so the current challenge measures query-form, compositional, answerability, and adversarial generalization—not pristine fact-family generalization.
4. **Expand unanswerable and hard-negative families before changing similarity thresholds.** MiniLM's configured threshold is too permissive, so encoder promotion and refusal calibration must be separate changes.
5. **Do not promote Qwen3 or keep BGE Small as the long-term default.** Qwen is disproportionately slow; BGE Small loses too much retrieval quality.
6. **Retain Portfolio GTE and BGE Base as selectable alternatives.** GTE is competitive across slices; BGE Base is useful when challenge recall matters more than memory.

## Validation and artifacts

- Repository tests: **92 passed**.
- Ruff: **all checks passed**.
- `git diff --check`: clean.
- Raw old-laptop artifacts: `evaluation/results/v2-full/`
  - `summary.json`
  - `environment.json`
  - `report.md`
  - six per-model raw JSONL files
  - `process.time`
- Compact machine-readable comparison: `evaluation/EVAL_V2_RESULTS.csv`
- Append-only implementation journal: `evaluation/EVAL_V2_JOURNAL.md`

Production defaults were not modified during this work.
