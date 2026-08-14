# Paired semantic-chunking evaluation: heldout

> Automatic and manual chunking use the same cases, six embedding routes, model revisions, and Top K. The source reports predate serialized protocol metadata; Top K and model/revision/dimension/device are artifact-verified, while candidate depth, query builder, selector, embedding-prefix, dtype, and score-threshold parity rely on their shared evaluator implementation. Confidence intervals are descriptive because the corpus and case sets are small.

## Sample and topology

- Answerable cases: **8**
- Required evidence groups: **9**
- Paired route/case observations: **48**
- Chunks: **22 automatic → 20 manual**
- Mean chunk words: **67.863636 → 77.25**

## Source-run absolute gates

- Automatic: **0/6 routes passed**; gates enforced during run: **False**
- Manual: **2/6 routes passed**; gates enforced during run: **False**

> These are the source evaluator's absolute thresholds. They are reported separately from paired automatic/manual regression statistics.

## Per-embedder retrieval table

| Embedder | R@1 | R@3 | R@5 | All evidence@5 | Mean evidence RR@5 | Required context P@5 | Redundancy@5 | Context chars@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bge-base | 0.438 → 0.625 (+0.188) | 0.438 → 0.875 (+0.438) | 0.562 → 1.000 (+0.438) | 0.500 → 1.000 (+0.500) | 0.469 → 0.760 (+0.292) | 0.125 → 0.200 (+0.075) | 0.098 → 0.093 (-0.005) | 2809.625 → 3491.875 (+682.250) |
| bge-small | 0.438 → 0.500 (+0.062) | 0.562 → 0.750 (+0.188) | 0.688 → 1.000 (+0.312) | 0.625 → 1.000 (+0.375) | 0.525 → 0.660 (+0.135) | 0.150 → 0.200 (+0.050) | 0.093 → 0.093 (+0.000) | 2875.875 → 3398.750 (+522.875) |
| minilm-l6 | 0.625 → 0.500 (-0.125) | 0.812 → 0.625 (-0.188) | 0.812 → 1.000 (+0.188) | 0.750 → 1.000 (+0.250) | 0.688 → 0.635 (-0.052) | 0.175 → 0.200 (+0.025) | 0.101 → 0.094 (-0.007) | 2813.500 → 3457.375 (+643.875) |
| portfolio-e5-small | 0.438 → 0.625 (+0.188) | 0.562 → 0.875 (+0.312) | 0.812 → 1.000 (+0.188) | 0.750 → 1.000 (+0.250) | 0.542 → 0.740 (+0.198) | 0.175 → 0.200 (+0.025) | 0.098 → 0.095 (-0.003) | 2750.250 → 3252.125 (+501.875) |
| portfolio-gte-small | 0.562 → 0.500 (-0.062) | 0.562 → 0.625 (+0.062) | 0.688 → 0.875 (+0.188) | 0.625 → 0.875 (+0.250) | 0.594 → 0.619 (+0.025) | 0.150 → 0.175 (+0.025) | 0.097 → 0.095 (-0.002) | 2808.250 → 3320.500 (+512.250) |
| qwen3-embedding | 0.562 → 0.500 (-0.062) | 0.812 → 1.000 (+0.188) | 0.812 → 1.000 (+0.188) | 0.750 → 1.000 (+0.250) | 0.646 → 0.708 (+0.062) | 0.175 → 0.200 (+0.025) | 0.094 → 0.097 (+0.003) | 2726.625 → 3319.125 (+592.500) |

## Macro paired uncertainty

Embedding routes are averaged within each case before cases are resampled, so six correlated model outputs are not treated as six independent questions.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI | W/T/L | Exact sign p |
|---|---:|---:|---:|---:|---:|---:|
| Evidence recall@1 | 0.510 | 0.542 | +0.031 | [-0.094, +0.135] | 3/4/1 | 0.6250 |
| Evidence recall@3 | 0.625 | 0.792 | +0.167 | [+0.042, +0.312] | 4/4/0 | 0.1250 |
| Evidence recall@5 | 0.729 | 0.979 | +0.250 | [+0.062, +0.479] | 4/4/0 | 0.1250 |
| All-evidence success@5 | 0.667 | 0.979 | +0.312 | [+0.062, +0.604] | 4/4/0 | 0.1250 |
| Mean evidence reciprocal rank@5 | 0.577 | 0.687 | +0.110 | [+0.009, +0.214] | 5/2/1 | 0.2188 |
| Required-context precision@5 | 0.158 | 0.196 | +0.037 | [+0.000, +0.083] | 3/5/0 | 0.2500 |
| Context token-set redundancy@5 | 0.097 | 0.095 | -0.002 | [-0.006, +0.002] | 5/0/3 | 0.7266 |
| Context characters@5 | 2797.354 | 3373.292 | +575.938 | [+373.354, +782.908] | descriptive | — |

## Fixed context-budget comparison

This controls the main Top-K confound: manual chunks are larger. Each row measures the production-formatted source excerpts, keeps the rank-preserving Top-5 prefix, and stops before adding a whole chunk that would exceed the budget.

| Budget | Evidence recall | All-evidence success | Actual chars (automatic → manual) | Chunks (automatic → manual) |
|---:|---:|---:|---:|---:|
| 1500 | 0.531 → 0.646 (+0.115) | 0.479 → 0.646 (+0.167) | 1212 → 1083 | 2.12 → 1.75 |
| 2000 | 0.625 → 0.729 (+0.104) | 0.562 → 0.729 (+0.167) | 1756 → 1697 | 3.06 → 2.54 |
| 2500 | 0.708 → 0.833 (+0.125) | 0.646 → 0.833 (+0.188) | 2225 → 2076 | 3.96 → 3.10 |

## Evidence-level regressions

- Coverage gains: **15**
- Coverage losses: **0**
- Rank improvements within Top 5: **6**
- Rank regressions within Top 5: **5**

## Metric definitions

- **R@K:** fraction of required evidence groups found by rank K.
- **All evidence@K:** fraction of questions for which every required evidence group is present by rank K.
- **Mean evidence RR@5:** reciprocal rank averaged across every evidence group, not only the first hit.
- **Required context P@5:** fraction of returned chunks matching required qrels; it is a lower bound because qrels do not label every merely useful chunk.
- **Redundancy@5:** mean pairwise Jaccard similarity between retrieved chunk token sets; lower means less repeated context.
- **Context chars@5:** production-formatted source-excerpt size; descriptive, not automatically better when smaller.
- **Fixed context budget:** evidence metrics after limiting production-formatted source excerpts to the same strict character ceiling; this separates boundary quality from simply returning more text.
