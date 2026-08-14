# Paired semantic-chunking evaluation: dev

> Automatic and manual chunking use the same cases, six embedding routes, model revisions, and Top K. The source reports predate serialized protocol metadata; Top K and model/revision/dimension/device are artifact-verified, while candidate depth, query builder, selector, embedding-prefix, dtype, and score-threshold parity rely on their shared evaluator implementation. Confidence intervals are descriptive because the corpus and case sets are small.

## Sample and topology

- Answerable cases: **13**
- Required evidence groups: **16**
- Paired route/case observations: **78**
- Chunks: **22 automatic → 20 manual**
- Mean chunk words: **67.863636 → 77.25**

## Source-run absolute gates

- Automatic: **0/6 routes passed**; gates enforced during run: **False**
- Manual: **6/6 routes passed**; gates enforced during run: **False**

> These are the source evaluator's absolute thresholds. They are reported separately from paired automatic/manual regression statistics.

## Per-embedder retrieval table

| Embedder | R@1 | R@3 | R@5 | All evidence@5 | Mean evidence RR@5 | Required context P@5 | Redundancy@5 | Context chars@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bge-base | 0.577 → 0.885 (+0.308) | 0.846 → 0.962 (+0.115) | 0.885 → 1.000 (+0.115) | 0.846 → 1.000 (+0.154) | 0.706 → 0.933 (+0.226) | 0.215 → 0.215 (+0.000) | 0.089 → 0.088 (-0.001) | 2690.615 → 3321.308 (+630.692) |
| bge-small | 0.500 → 0.923 (+0.423) | 0.923 → 0.962 (+0.038) | 0.923 → 1.000 (+0.077) | 0.846 → 1.000 (+0.154) | 0.692 → 0.946 (+0.253) | 0.215 → 0.215 (+0.000) | 0.086 → 0.090 (+0.004) | 2731.308 → 3307.154 (+575.846) |
| minilm-l6 | 0.385 → 0.692 (+0.308) | 0.885 → 0.962 (+0.077) | 0.923 → 1.000 (+0.077) | 0.846 → 1.000 (+0.154) | 0.631 → 0.830 (+0.199) | 0.215 → 0.215 (+0.000) | 0.084 → 0.083 (-0.002) | 2680.000 → 3309.923 (+629.923) |
| portfolio-e5-small | 0.731 → 0.846 (+0.115) | 0.885 → 0.962 (+0.077) | 0.923 → 1.000 (+0.077) | 0.846 → 1.000 (+0.154) | 0.803 → 0.913 (+0.111) | 0.215 → 0.215 (+0.000) | 0.084 → 0.083 (-0.000) | 2692.462 → 3056.538 (+364.077) |
| portfolio-gte-small | 0.615 → 0.885 (+0.269) | 0.923 → 1.000 (+0.077) | 0.923 → 1.000 (+0.077) | 0.846 → 1.000 (+0.154) | 0.756 → 0.942 (+0.186) | 0.215 → 0.215 (+0.000) | 0.089 → 0.086 (-0.003) | 2682.615 → 3098.231 (+415.615) |
| qwen3-embedding | 0.731 → 0.923 (+0.192) | 0.731 → 0.962 (+0.231) | 0.923 → 1.000 (+0.077) | 0.923 → 1.000 (+0.077) | 0.775 → 0.946 (+0.171) | 0.231 → 0.215 (-0.015) | 0.084 → 0.090 (+0.007) | 2587.769 → 3209.308 (+621.538) |

## Macro paired uncertainty

Embedding routes are averaged within each case before cases are resampled, so six correlated model outputs are not treated as six independent questions.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI | W/T/L | Exact sign p |
|---|---:|---:|---:|---:|---:|---:|
| Evidence recall@1 | 0.590 | 0.859 | +0.269 | [+0.109, +0.462] | 8/5/0 | 0.0078 |
| Evidence recall@3 | 0.865 | 0.968 | +0.103 | [+0.026, +0.192] | 5/8/0 | 0.0625 |
| Evidence recall@5 | 0.917 | 1.000 | +0.083 | [+0.013, +0.167] | 4/9/0 | 0.1250 |
| All-evidence success@5 | 0.859 | 1.000 | +0.141 | [+0.013, +0.308] | 4/9/0 | 0.1250 |
| Mean evidence reciprocal rank@5 | 0.727 | 0.918 | +0.191 | [+0.082, +0.312] | 8/5/0 | 0.0078 |
| Required-context precision@5 | 0.218 | 0.215 | -0.003 | [-0.046, +0.038] | 3/8/2 | 1.0000 |
| Context token-set redundancy@5 | 0.086 | 0.087 | +0.001 | [-0.006, +0.008] | 8/0/5 | 0.5811 |
| Context characters@5 | 2677.462 | 3217.077 | +539.615 | [+403.973, +689.951] | descriptive | — |

## Fixed context-budget comparison

This controls the main Top-K confound: manual chunks are larger. Each row measures the production-formatted source excerpts, keeps the rank-preserving Top-5 prefix, and stops before adding a whole chunk that would exceed the budget.

| Budget | Evidence recall | All-evidence success | Actual chars (automatic → manual) | Chunks (automatic → manual) |
|---:|---:|---:|---:|---:|
| 1500 | 0.795 → 0.917 (+0.122) | 0.744 → 0.910 (+0.167) | 1221 → 1142 | 2.28 → 1.83 |
| 2000 | 0.865 → 0.949 (+0.083) | 0.808 → 0.936 (+0.128) | 1695 → 1708 | 3.17 → 2.69 |
| 2500 | 0.891 → 0.968 (+0.077) | 0.821 → 0.936 (+0.115) | 2177 → 2098 | 4.08 → 3.33 |

## Evidence-level regressions

- Coverage gains: **11**
- Coverage losses: **0**
- Rank improvements within Top 5: **22**
- Rank regressions within Top 5: **1**

## Metric definitions

- **R@K:** fraction of required evidence groups found by rank K.
- **All evidence@K:** fraction of questions for which every required evidence group is present by rank K.
- **Mean evidence RR@5:** reciprocal rank averaged across every evidence group, not only the first hit.
- **Required context P@5:** fraction of returned chunks matching required qrels; it is a lower bound because qrels do not label every merely useful chunk.
- **Redundancy@5:** mean pairwise Jaccard similarity between retrieved chunk token sets; lower means less repeated context.
- **Context chars@5:** production-formatted source-excerpt size; descriptive, not automatically better when smaller.
- **Fixed context budget:** evidence metrics after limiting production-formatted source excerpts to the same strict character ceiling; this separates boundary quality from simply returning more text.
