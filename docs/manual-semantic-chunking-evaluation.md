# Manual semantic chunking: before/after evaluation

- **Audit date:** 2026-08-14
- **Baseline:** `a855b7b147ebc4e8c28699a6cf35b53ac4958ecb` (automatic, 22 chunks)
- **Final manual candidate:** `f16acb248c47a317baa16eb5d206bfe6adbcc8e1` (20 chunks)
- **Production deployment containing the candidate:** `9ed3a777f1a9c5ee74b292cb577bcc469d6aa801`

## Verdict

The manual 20-chunk corpus has strong retrospective retrieval evidence against the exact 22-chunk
baseline. Across the six unchanged embedding routes, it recovers more required evidence, ranks it
earlier, and has no Top-5 evidence-coverage losses on the development or legacy held-out cases.
The mean gain remains under fixed 1,500/2,000/2,500-character context budgets. On the fresh
challenge, the 1,500- and 2,000-character intervals are positive; the 2,500-character interval
crosses zero. Larger manual chunks contribute context, but do not explain the strongest gains.

The sealed `challenge-v2` first-look run also supports generalization: all six routes improved or
tied on Top-5 required-evidence coverage, with 16 evidence recoveries and no losses. A sensitivity
bootstrap over 15 shared-fact clusters retains positive intervals for the core retrieval gains. The
remaining caveats are:

1. The old `heldout.json` was evaluated against three successive manual corpora. It is useful
   regression data, but no longer an untouched held-out split.
2. One-shot DeepSeek V4 Flash answer evaluation improved factual completeness but produced one
   prompt-injection contract loss.
3. Three-run safety evaluation showed no refusal or forbidden-claim regression, but citation-format
   variance reduced the aggregate pass rate on one unsupported-salary case.
4. This remains a small, portfolio-specific corpus. The 18 answerable challenge cases are useful
   paired evidence, not a claim of universal retrieval quality.

Accordingly:

- **Paired chunking comparison:** pass; required-evidence coverage improved with no Top-5 losses.
- **Existing absolute route gates:** not a full pass. Manual passed 6/6 routes on dev, 2/6 on the
  reused held-out split, and 4/6 on challenge v2.
- **Generated-answer evidence:** positive but mixed; not a clean safety pass.
- **Overall strict all-gates verdict:** fail/incomplete; the evidence supports manual chunking over
  automatic chunking but does not justify claiming that every pre-existing threshold passes.
- **Production action from this audit branch:** none. Production was not re-ingested or modified.

## What existed before

The baseline used deterministic heading-aware automatic chunking:

| Setting | Baseline |
|---|---:|
| Maximum chunk size | 650 characters |
| Character overlap | 60 |
| Minimum chunk size | 90 characters |
| Corpus chunks | 22 |
| Database chunk IDs | deterministic, content-derived |
| Manual semantic markers | none |

The evaluator already had useful foundations:

- 16 development cases, including 13 answerable retrieval cases;
- 10 legacy held-out cases, including 8 answerable retrieval cases;
- six embedding routes with fixed query/document prefixes;
- exact cosine ranking, candidate depth 12, diversity selection, and Top 5 retrieval evaluation;
- source/content qrels, answer contracts, refusal cases, typo cases, and history cases;
- Recall@1/3/5, first-hit MRR@5, and required-evidence coverage;
- live SSE answer evaluation with citation, refusal, forbidden-claim, and completion gates.

The weaknesses were mainly methodological rather than missing infrastructure:

- aggregate scores hid per-evidence and per-case regressions;
- first-hit MRR rewarded finding one evidence group even when another was missed;
- there were no paired confidence intervals or win/tie/loss counts;
- context precision, redundancy, and size were not measured;
- fixed Top K did not control for larger manual chunks;
- answer runs were summarized without a strict paired comparator or explicit provider-exclusion
  policy;
- offline and DB-backed evaluators duplicated retrieval-query construction;
- the legacy held-out split's repeated use was not disclosed clearly enough.

## What changed

### Corpus and parser

Reviewed markers use:

```html
<!-- rag-chunk: <stable-id> | <descriptive-title> -->
```

The final corpus has 20 manual semantic chunks. Marker IDs are author-facing labels; database IDs
remain deterministic and content-derived. Unmarked documents still use the original heading-aware
automatic chunker. Duplicate, malformed, inline, and marker-like malformed comments fail closed.

The candidate preserves the ordered corpus body: all 1,335 baseline words remain in the same order.
Only marker comments and boundary placement were added. The exact reconstructed automatic corpus
hash is still:

```text
f5d7cfc823f4f4fb08fe9a10a913fb5e9197c7517b7d50f93dc7421f5f2a7042
```

The final manual corpus hash is:

```text
7ddd7a8bb8a3d110a9388d8977347c8332a7c140b421a153b6ce5948172b07ed
```

The paired comparator now rebuilds both corpora and fails if either hash differs from its preserved
source report.

### Shared query construction

`app/retrieval_query.py` is now the single retrieval-query implementation used by:

- live API retrieval;
- DB-backed retrieval evaluation;
- offline automatic/manual evaluation.

It preserves the production history policy: only prior user messages among the last four history
messages are prepended, and `use_history=False` disables the prefix.

### Retrieval metrics

Every answerable route/case row now reports:

- Recall@1/3/5 across all required evidence groups;
- first-hit reciprocal rank and mean reciprocal rank across every evidence group;
- complete-evidence success at 1/3/5;
- required-context precision at Top 5;
- context token-set redundancy;
- source diversity and total context characters;
- evidence coverage and complete-evidence success under 1,500/2,000/2,500-character budgets.

`requiredContextPrecisionAt5` is deliberately named narrowly: qrels contain required evidence, not
an exhaustive list of every potentially useful passage. It is a lower-bound noise diagnostic, not
classical exhaustive precision.

### Paired statistics and regression output

`scripts.compare_chunking_runs` now:

- pairs strictly on `(caseId, embedder)` and rejects missing, duplicate, or mismatched rows;
- validates split, question, Top K, route model/revision/dimension, and corpus-hash parity;
- uses 10,000 deterministic paired bootstrap samples;
- resamples cases, keeping six route observations for a case together;
- reports exact two-sided sign tests, with ties excluded;
- reports route, macro, and category tables;
- emits explicit evidence-level coverage gains/losses and rank improvements/regressions;
- emits machine-readable JSON and deterministic Markdown.

The preserved dev/held-out summaries and the first challenge summaries predate serialized
`retrievalProtocol` and full `embeddingRoutes` metadata. Their artifacts directly prove case, Top K,
route model/revision/dimension/device, corpus hash, and paired row parity. Candidate depth,
query-builder, diversity-selector settings, query/document prefixes, dtype, and minimum score come
from the shared evaluator implementation rather than independent source-artifact fields. Future
offline reports now serialize those values, and the comparator rejects mismatches. No retrieval
result was rerun or altered to fill this provenance gap retroactively.

No multiple-comparison correction is applied. Confidence intervals and sign tests are descriptive
because the sample is small and route results for the same question are correlated.

### Paired answer evaluation

`scripts.compare_answer_runs` pairs answer requests by case, repeat, embedder, and model. It reports:

- contract pass rate;
- required-claim, refusal, forbidden-claim, and citation gates;
- claim-group, retrieved-evidence, and cited-evidence coverage;
- valid citation references;
- latency, token use, and provider-reported cost;
- pass gains/losses and category summaries.

Provider failures, incomplete streams, fallback models, and served-model mismatches are listed but
excluded from quality wins/losses. A clean local refusal is explicitly marked and remains a scored
quality outcome even though it has no provider model event. Full request payloads must match before
rows can pair. Repeated runs are averaged within case before bootstrapping, so three repeats are not
misrepresented as three independent questions.

### New challenge split

`evaluation/challenge-v2.json` contains 22 post-deployment robustness cases:

- 18 answerable cases;
- 4 refusal/prompt-injection cases;
- paraphrase, compositional, follow-up, noisy-query, and privacy-boundary axes;
- explicit fact-family metadata and source/content qrels.

It was authored after the final 20-chunk corpus was frozen, remapped without reading retrieval
scores, and sealed before its first run:

```text
c259a18cac1ca7d652e5f8c70aef35112c596bd490a489957f3cde5177613842
```

Its first six-embedder run was completed on 2026-08-14. That result is reported below. The split is
now regression data and must not be used to tune another candidate.

## Retrieval results

### Sealed `challenge-v2` first-look split

Eighteen answerable cases × six routes = 108 paired route/case observations. Four refusal cases are
retained for answer evaluation and correctly excluded from retrieval scoring.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI | W/T/L by case |
|---|---:|---:|---:|---:|---:|
| Evidence Recall@1 | 0.551 | 0.731 | +0.181 | [+0.037, +0.347] | 8/8/2 |
| Evidence Recall@3 | 0.759 | 0.944 | +0.185 | [+0.065, +0.333] | 8/10/0 |
| Evidence Recall@5 | 0.866 | 0.968 | +0.102 | [+0.019, +0.213] | 5/13/0 |
| Complete evidence@5 | 0.833 | 0.954 | +0.120 | [+0.019, +0.250] | 4/14/0 |
| Mean reciprocal evidence rank@5 | 0.664 | 0.830 | +0.166 | [+0.057, +0.296] | 9/7/2 |
| Required-context precision@5 | 0.194 | 0.220 | +0.026 | [+0.004, +0.054] | 5/13/0 |
| Context redundancy@5 | 0.094 | 0.091 | -0.002 | [-0.007, +0.002] | 9/0/9 |
| Context characters@5 | 2,795 | 3,388 | +594 | [+493, +694] | descriptive |

Evidence-level change counts across all six routes:

- coverage gains: **16**;
- coverage losses: **0**;
- within-Top-5 rank improvements: **36**;
- within-Top-5 rank regressions: **8**.

Every route improved Recall@5. Qwen had the largest gain, 0.778→0.972 (+0.194), and MiniLM
reached 1.000 (+0.139). BGE-base was already strong and moved 0.944→0.972 (+0.028). No route lost
complete-evidence success; BGE-base tied while the other five improved.

The source runner was executed with `--no-gate` so both variants would finish and remain pairable.
Its absolute gates were still calculated and preserved. Automatic passed 0/6 routes. Manual passed
4/6: BGE-small and portfolio-GTE-small each reached Recall@5 0.944, narrowly below the existing
0.950 threshold. Thus the paired regression comparison passes, while the old absolute all-route
gate does not.

The 18 cases form 15 connected fact clusters because three query variants share fact IDs. A
deterministic cluster bootstrap keeps those related variants together. Its 95% intervals remain
positive for Recall@1 `[+0.032, +0.359]`, Recall@3 `[+0.059, +0.338]`, Recall@5
`[+0.021, +0.221]`, complete evidence@5 `[+0.017, +0.267]`, mean reciprocal evidence rank
`[+0.051, +0.311]`, and required-context precision `[+0.005, +0.055]`. Redundancy remains
indistinguishable from zero.

### Development split

Thirteen answerable cases × six routes = 78 paired route/case observations. The macro bootstrap unit
is case, not route/case row.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI | W/T/L by case |
|---|---:|---:|---:|---:|---:|
| Evidence Recall@1 | 0.590 | 0.859 | +0.269 | [+0.109, +0.462] | 8/5/0 |
| Evidence Recall@3 | 0.865 | 0.968 | +0.103 | [+0.026, +0.192] | 5/8/0 |
| Evidence Recall@5 | 0.917 | 1.000 | +0.083 | [+0.013, +0.167] | 4/9/0 |
| Complete evidence@5 | 0.859 | 1.000 | +0.141 | [+0.013, +0.308] | 4/9/0 |
| Mean reciprocal evidence rank@5 | 0.727 | 0.918 | +0.191 | [+0.082, +0.312] | 8/5/0 |
| Required-context precision@5 | 0.218 | 0.215 | -0.003 | [-0.046, +0.038] | 3/8/2 |
| Context redundancy@5 | 0.086 | 0.087 | +0.001 | [-0.006, +0.008] | 8/0/5 |
| Context characters@5 | 2,677 | 3,217 | +540 | [+404, +690] | descriptive |

Evidence-level change counts across all six routes:

- coverage gains: **11**;
- coverage losses: **0**;
- within-Top-5 rank improvements: **22**;
- within-Top-5 rank regressions: **1**.

The manual development run passed the source evaluator's absolute gates on all six routes; the
automatic baseline passed 0/6.

### Legacy held-out split

Eight answerable cases × six routes = 48 paired route/case observations. These numbers are useful
for regression inspection but not a clean generalization estimate because multiple manual corpora
were evaluated on this split.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI | W/T/L by case |
|---|---:|---:|---:|---:|---:|
| Evidence Recall@1 | 0.510 | 0.542 | +0.031 | [-0.094, +0.135] | 3/4/1 |
| Evidence Recall@3 | 0.625 | 0.792 | +0.167 | [+0.042, +0.312] | 4/4/0 |
| Evidence Recall@5 | 0.729 | 0.979 | +0.250 | [+0.062, +0.479] | 4/4/0 |
| Complete evidence@5 | 0.667 | 0.979 | +0.312 | [+0.062, +0.604] | 4/4/0 |
| Mean reciprocal evidence rank@5 | 0.577 | 0.687 | +0.110 | [+0.009, +0.214] | 5/2/1 |
| Required-context precision@5 | 0.158 | 0.196 | +0.037 | [+0.000, +0.083] | 3/5/0 |
| Context redundancy@5 | 0.097 | 0.095 | -0.002 | [-0.006, +0.002] | 5/0/3 |
| Context characters@5 | 2,797 | 3,373 | +576 | [+373, +783] | descriptive |

Evidence-level change counts across all six routes:

- coverage gains: **15**;
- coverage losses: **0**;
- within-Top-5 rank improvements: **6**;
- within-Top-5 rank regressions: **5**.

The manual legacy-held-out run passed the source evaluator's absolute gates on only 2/6 routes;
the automatic baseline passed 0/6. Because this split was reused during candidate iteration, that
failure is reported as regression evidence rather than used to retune the corpus.

The important route-level exception is MiniLM on this reused split: Recall@5 improved from 0.812 to
1.000, while mean reciprocal evidence rank fell from 0.688 to 0.635. Coverage improved, but some
already-retrievable evidence moved later.

### Route table

Values are automatic → manual (delta).

| Split | Route | Recall@5 | Complete evidence@5 | Mean reciprocal evidence rank@5 |
|---|---|---:|---:|---:|
| Challenge v2 | bge-base | 0.944→0.972 (+0.028) | 0.944→0.944 (0.000) | 0.716→0.870 (+0.155) |
| Challenge v2 | bge-small | 0.861→0.944 (+0.083) | 0.833→0.944 (+0.111) | 0.696→0.759 (+0.063) |
| Challenge v2 | minilm-l6 | 0.861→1.000 (+0.139) | 0.833→1.000 (+0.167) | 0.598→0.794 (+0.196) |
| Challenge v2 | portfolio-e5-small | 0.889→0.972 (+0.083) | 0.833→0.944 (+0.111) | 0.657→0.910 (+0.253) |
| Challenge v2 | portfolio-gte-small | 0.861→0.944 (+0.083) | 0.833→0.944 (+0.111) | 0.662→0.782 (+0.120) |
| Challenge v2 | qwen3-embedding | 0.778→0.972 (+0.194) | 0.722→0.944 (+0.222) | 0.655→0.866 (+0.211) |
| Dev | bge-base | 0.885→1.000 (+0.115) | 0.846→1.000 (+0.154) | 0.706→0.933 (+0.226) |
| Dev | bge-small | 0.923→1.000 (+0.077) | 0.846→1.000 (+0.154) | 0.692→0.946 (+0.253) |
| Dev | minilm-l6 | 0.923→1.000 (+0.077) | 0.846→1.000 (+0.154) | 0.631→0.830 (+0.199) |
| Dev | portfolio-e5-small | 0.923→1.000 (+0.077) | 0.846→1.000 (+0.154) | 0.803→0.913 (+0.111) |
| Dev | portfolio-gte-small | 0.923→1.000 (+0.077) | 0.846→1.000 (+0.154) | 0.756→0.942 (+0.186) |
| Dev | qwen3-embedding | 0.923→1.000 (+0.077) | 0.923→1.000 (+0.077) | 0.775→0.946 (+0.171) |
| Legacy held-out | bge-base | 0.562→1.000 (+0.438) | 0.500→1.000 (+0.500) | 0.469→0.760 (+0.292) |
| Legacy held-out | bge-small | 0.688→1.000 (+0.312) | 0.625→1.000 (+0.375) | 0.525→0.660 (+0.135) |
| Legacy held-out | minilm-l6 | 0.812→1.000 (+0.188) | 0.750→1.000 (+0.250) | 0.688→0.635 (-0.052) |
| Legacy held-out | portfolio-e5-small | 0.812→1.000 (+0.188) | 0.750→1.000 (+0.250) | 0.542→0.740 (+0.198) |
| Legacy held-out | portfolio-gte-small | 0.688→0.875 (+0.188) | 0.625→0.875 (+0.250) | 0.594→0.619 (+0.025) |
| Legacy held-out | qwen3-embedding | 0.812→1.000 (+0.188) | 0.750→1.000 (+0.250) | 0.646→0.708 (+0.062) |

### Fixed context-budget control

The manual Top-5 contexts contain roughly 21% more production-formatted source-excerpt characters.
To test whether that alone explains the gain, the comparator takes the selected Top-5 prefix that
fits each strict character budget. It counts the exact `[S#] title (source)\ncontent` representation
used in the prompt and never includes a chunk that would exceed the ceiling. It does not rerank,
truncate, or split chunks.

| Split | Budget | Evidence Recall, automatic→manual | Complete evidence, automatic→manual |
|---|---:|---:|---:|
| Challenge v2 | 1,500 | 0.671→0.838 (+0.167) | 0.630→0.815 (+0.185) |
| Challenge v2 | 2,000 | 0.764→0.884 (+0.120) | 0.722→0.861 (+0.139) |
| Challenge v2 | 2,500 | 0.801→0.898 (+0.097) | 0.759→0.870 (+0.111) |
| Dev | 1,500 | 0.795→0.917 (+0.122) | 0.744→0.910 (+0.167) |
| Dev | 2,000 | 0.865→0.949 (+0.083) | 0.808→0.936 (+0.128) |
| Dev | 2,500 | 0.891→0.968 (+0.077) | 0.821→0.936 (+0.115) |
| Legacy held-out | 1,500 | 0.531→0.646 (+0.115) | 0.479→0.646 (+0.167) |
| Legacy held-out | 2,000 | 0.625→0.729 (+0.104) | 0.562→0.729 (+0.167) |
| Legacy held-out | 2,500 | 0.708→0.833 (+0.125) | 0.646→0.833 (+0.188) |

The challenge recall and complete-evidence intervals are positive at 1,500 and 2,000 characters;
both cross zero at 2,500 despite positive means. The dev intervals remain positive at every budget.
The reused held-out intervals cross zero at all three budgets. The strongest fresh fixed-budget
evidence therefore sits at the tighter 1,500/2,000-character controls, not every ceiling.

## Generated-answer results

### Single-run factual/general set

Sixteen paired DeepSeek V4 Flash requests; no provider failures or fallbacks were excluded.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI |
|---|---:|---:|---:|---:|
| Full contract pass | 0.625 | 0.812 | +0.188 | [-0.062, +0.438] |
| Required-claim gate | 0.688 | 0.938 | +0.250 | [+0.062, +0.500] |
| Claim-group coverage | 0.859 | 0.962 | +0.103 | [+0.000, +0.218] |
| Citation gate | 0.812 | 0.875 | +0.062 | [-0.125, +0.250] |
| Retrieved evidence coverage@3 | 0.923 | 1.000 | +0.077 | [+0.000, +0.192] |
| Cited evidence coverage | 0.923 | 1.000 | +0.077 | [+0.000, +0.192] |
| Mean total latency | 5.81 s | 9.46 s | +3.65 s | [-1.49 s, +8.54 s] |
| Mean total tokens | 974 | 1,059 | +85 | [+11, +165] |
| Mean reported cost | $0.000105 | $0.000137 | +$0.000032 | [-$0.000006, +$0.000069] |

There were four full-pass gains and one loss. All four gains were grounded-claim improvements; the
loss was `dev-refuse-prompt-injection`, where the manual run failed the refusal and citation gates.
This is one stochastic sample and must be repeated before treating it as a persistent safety
regression.

### Three-run safety subset

Three refusal cases × three repeats = nine aligned requests. Repeats are averaged by case before
bootstrap analysis. No request had a provider error, fallback, failed refusal, or forbidden claim.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI |
|---|---:|---:|---:|---:|
| Full contract pass | 0.556 | 0.444 | -0.111 | [-0.333, +0.000] |
| Refusal gate | 1.000 | 1.000 | 0.000 | [0.000, 0.000] |
| Forbidden-claim gate | 1.000 | 1.000 | 0.000 | [0.000, 0.000] |
| Citation gate | 0.556 | 0.444 | -0.111 | [-0.333, +0.000] |

The pass-rate difference came entirely from citation-format flips on
`dev-refuse-unsupported-salary`: one manual gain and two manual losses across three repeats. This is
variance, not evidence of a new fabricated claim, but it still prevents calling the answer layer a
clean pass.

## Proposed future gate

Freeze this policy before scoring a future candidate:

1. Corpus-body preservation and marker/parser tests must pass.
2. Automatic and manual report corpus hashes must match the frozen lineage.
3. No required-evidence Top-5 coverage loss for any case/route.
4. Macro evidence Recall@5 and complete-evidence@5 must be non-inferior under the 2,000-character
   budget; use a predeclared margin of -0.02.
5. Report every route and evidence-level regression; aggregate gain cannot hide a critical loss.
6. No forbidden-claim regression.
7. Prompt-injection and unsupported-request cases must pass repeated answer runs; citation-only
   failures must be reported separately from refusal/claim failures.
8. Provider errors and fallbacks must not be counted as quality outcomes; clean local refusals must.
9. The sealed challenge has now been viewed once and is regression-only; never tune against it.
10. Only after offline and answer gates pass should production be re-ingested and live SSE
    answers/citations verified.

Because the sample is small, do not require a conventional `p < 0.05` claim. Use strict regression
lists, paired intervals, effect sizes, and operational gates instead.

## Reproduction

### Tests

```bash
pytest -q
ruff check .
```

### Regrade preserved automatic/manual rankings

```bash
python -m scripts.compare_chunking_runs \
  --automatic-dir <reports>/final-auto-dev \
  --manual-dir <reports>/final-v3-manual-dev \
  --split dev --bootstrap-samples 10000 --seed 20260814 \
  --output-json evaluation/manual-chunking-dev-rigorous.json \
  --output-markdown evaluation/manual-chunking-dev-rigorous.md

python -m scripts.compare_chunking_runs \
  --automatic-dir <reports>/final-auto-heldout \
  --manual-dir <reports>/final-v3-manual-heldout \
  --split heldout --bootstrap-samples 10000 --seed 20260814 \
  --output-json evaluation/manual-chunking-heldout-rigorous.json \
  --output-markdown evaluation/manual-chunking-heldout-rigorous.md
```

The comparator recomputes all metrics from preserved JSONL rankings and current semantic qrels. It
does not regenerate embeddings for these two reports.

### Recorded first challenge run / future exact replay

Run automatic and manual evaluations on the same machine, artifact tree, device, and checkout:

```bash
python -m scripts.evaluate_chunking_offline \
  --split challenge-v2 --chunking auto --device cpu \
  --artifact-root <model-artifacts> \
  --output-dir <reports>/challenge-v2-auto --no-gate

python -m scripts.evaluate_chunking_offline \
  --split challenge-v2 --chunking manual --device cpu \
  --artifact-root <model-artifacts> \
  --output-dir <reports>/challenge-v2-manual --no-gate

python -m scripts.compare_chunking_runs \
  --automatic-dir <reports>/challenge-v2-auto \
  --manual-dir <reports>/challenge-v2-manual \
  --split challenge-v2 --bootstrap-samples 10000 --seed 20260814 \
  --output-json evaluation/manual-chunking-challenge-v2-rigorous.json \
  --output-markdown evaluation/manual-chunking-challenge-v2-rigorous.md
```

The first result has been read. Do not edit `challenge-v2.json`, qrels, corpus boundaries, gates, or
model settings in response to it.

### Regrade generated answers

```bash
python -m scripts.compare_answer_runs \
  --automatic-dir <reports>/answer-auto-deepseek \
  --manual-dir <reports>/answer-v3-deepseek \
  --bootstrap-samples 10000 --seed 20260814 \
  --output-json evaluation/manual-chunking-answer-rigorous.json \
  --output-markdown evaluation/manual-chunking-answer-rigorous.md
```

## Machine-readable evidence

- [`manual-chunking-dev-rigorous.json`](../evaluation/manual-chunking-dev-rigorous.json)
- [`manual-chunking-heldout-rigorous.json`](../evaluation/manual-chunking-heldout-rigorous.json)
- [`manual-chunking-challenge-v2-rigorous.json`](../evaluation/manual-chunking-challenge-v2-rigorous.json)
- [`manual-chunking-answer-rigorous.json`](../evaluation/manual-chunking-answer-rigorous.json)
- [`manual-chunking-safety-rigorous.json`](../evaluation/manual-chunking-safety-rigorous.json)
- [`manual-chunking-benchmark.json`](../evaluation/manual-chunking-benchmark.json)
- [`challenge-v2.json`](../evaluation/challenge-v2.json)
- [`challenge-v2.sha256`](../evaluation/challenge-v2.sha256)

The richer JSON reports include all route/category tables, confidence intervals, sign-test values,
input hashes, split/lock hashes, chunk topology, shared-fact sensitivity intervals, absolute source
gate status, and evidence-level regression lists. Stable `archive:` labels map to an operator-side
SHA-256 manifest; raw answers and held-out questions are not committed. Comparison summaries also
intentionally omit held-out question text.
