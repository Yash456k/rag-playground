# Portfolio RAG evaluation V2

This evaluation measures retrieval only. It discovers and chunks the corpus
with the production ingestion functions, encodes it in memory, retrieves
`min(12, top_k * 3)` stable exact-cosine candidates, and applies the production
diversity selector before scoring the final `top_k`. It does
not connect to PostgreSQL, invoke an LLM judge, or generate answers.

## Old-laptop setup

From the repository root on Ubuntu 24.04:

```bash
git switch eval-v2
python3.12 -m venv .venv-eval
.venv-eval/bin/python -m pip install --upgrade pip
.venv-eval/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv-eval/bin/python -m pytest -q
.venv-eval/bin/ruff check .
```

Place fine-tuned artifacts at
`model-artifacts/portfolio-e5-small-v1/` and
`model-artifacts/portfolio-gte-small-v1/`. Remote Hugging Face routes use the
40-character revisions pinned in `config/pipeline.yaml`; remote code is never
trusted. To use a different artifact directory, pass `--artifact-root`.

Validate data without loading any model:

```bash
.venv-eval/bin/python -c "from evaluation.v2.eval_lib import load_data; print(len(load_data()[1]))"
```

Run useful benchmark subsets:

```bash
# Basic development set
.venv-eval/bin/python scripts/evaluate_embeddings_v2.py --tier basic --split dev --device auto

# Intermediate development set, one model
.venv-eval/bin/python scripts/evaluate_embeddings_v2.py --tier intermediate --split dev --embedder bge-small

# Locked challenge set
.venv-eval/bin/python scripts/evaluate_embeddings_v2.py --split challenge

# All 120 queries and all six configured models, sequentially
.venv-eval/bin/python scripts/evaluate_embeddings_v2.py --tier all --split all --device auto \
  --artifact-root model-artifacts --warmup 1 --timing-runs 3 --bootstrap-samples 2000 \
  --seed 17 --top-k 5 --output-dir evaluation/results/v2
```

`--embedder` is repeatable and also accepts commas. `--device` is `auto`,
`cpu`, or `cuda`. Auto uses CUDA when available. Qwen's configured bfloat16 is
changed to float16 on CUDA for the GTX 1650 Ti; CPU retains the configured
dtype. Models are loaded, measured, deleted, garbage-collected, and followed by
a CUDA-cache release one at a time.

## Data semantics

`knowledge_map.json` contains atomic claims and exact evidence anchors.
`basic.json` covers direct lookup and short supported summaries.
`intermediate.json` covers paraphrase, noise, synthesis, history-dependent
follow-ups, related negatives, ambiguous or unsupported questions, false
premises, partial answerability, and injection attempts.

Each intent family has exactly three meaning-preserving but materially different
questions. A family belongs wholly to one tier and split. The files contain 40
families/120 cases: 28 development families/84 cases and 12 challenge
families/36 cases. Relevance grades range from 0 to 3; grade 3 is required
claim evidence, while grades 1 and 2 identify useful supporting context. Hard
negatives are plausible but wrong chunks and remain separate from qrels. `answer`, `refuse`,
and `clarify` describe downstream behavior, although V2 benchmarks retrieval
and score calibration only.

Every case records `training_overlap` and `generalization_axis`. The existing
training questions expose most direct corpus facts, so this is not a pristine
fact-family-held-out benchmark. The locked challenge measures held-out query
forms plus compositional, noisy, follow-up, contrastive, answerability, and
adversarial generalization over largely seen facts. Do not describe it as a
clean factual holdout.

The challenge lock hashes a canonical, key-sorted UTF-8 JSON serialization of
the challenge cases, independent of whitespace in the tier files. Regenerate
data and the lock only after an intentional review:

```bash
.venv-eval/bin/python -m evaluation.v2.build_data
```

## Reading results

The output directory contains per-model raw JSONL, `summary.json`,
`report.md`, and `environment.json`. Compare dev and challenge separately.
The pooled all-split view is informational and is never a release gate.
Retrieval relevance metrics and family consistency use answerable cases only;
each view reports both total and answerable query counts. Hard-negative hit
rates use only cases that define hard negatives. Required-evidence recall asks
whether grade-3 chunks were found; all-required
success is stricter for synthesis; nDCG rewards graded ordering; hard-negative
hit rate is lower-is-better. Family consistency averages the worst variant in
each family. Confidence intervals resample whole families, not individual
variants. Threshold diagnostics report both the current per-model value from
`config/pipeline.yaml` and a development-calibrated alternative. The challenge
set is always evaluated with the fixed development threshold; it is never
optimized on challenge scores. A challenge-only run has no development rows,
so the calibrated threshold is explicitly unavailable. Threshold diagnostics
use both answerable and unanswerable rows.

Paired W/T/L and deltas are emitted separately for dev/basic,
dev/intermediate, dev/all, challenge/basic, challenge/intermediate, and
challenge/all when present. Pooled all/all comparisons are informational only.

Timings separate encoding, exact ranking plus diversity selection, and
end-to-end query work (mean/p50/p95), along with observed loop wall time and
throughput. CUDA reports peak allocated and reserved MiB; host RSS is sampled
before load, after warmup, and after corpus encoding. Timings are reproducible
run measurements, not universal hardware claims.
Inspect the environment manifest before comparing runs. A model failure is
recorded and the remaining routes continue; the command fails only when all
requested models fail or validation fails.

## Leakage rule

Use dev for iteration. Do not train, tune prefixes, select thresholds, or choose
models from challenge questions. Once challenge questions or results have been
inspected, that set is regression data, not a blind benchmark. Create and lock
a fresh challenge set for the next unbiased model-selection decision.
