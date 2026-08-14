# Paired semantic-chunking evaluation: challenge-v2

> Automatic and manual chunking use the same cases, six embedding routes, model revisions, and Top K. The source reports predate serialized protocol metadata; Top K and model/revision/dimension/device are artifact-verified, while candidate depth, query builder, selector, embedding-prefix, dtype, and score-threshold parity rely on their shared evaluator implementation. Confidence intervals are descriptive because the corpus and case sets are small.

## Sample and topology

- Answerable cases: **18**
- Required evidence groups: **22**
- Paired route/case observations: **108**
- Chunks: **22 automatic → 20 manual**
- Mean chunk words: **67.863636 → 77.25**

## Source-run absolute gates

- Automatic: **0/6 routes passed**; gates enforced during run: **False**
- Manual: **4/6 routes passed**; gates enforced during run: **False**

> These are the source evaluator's absolute thresholds. They are reported separately from paired automatic/manual regression statistics.

## Per-embedder retrieval table

| Embedder | R@1 | R@3 | R@5 | All evidence@5 | Mean evidence RR@5 | Required context P@5 | Redundancy@5 | Context chars@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bge-base | 0.611 → 0.778 (+0.167) | 0.750 → 0.972 (+0.222) | 0.944 → 0.972 (+0.028) | 0.944 → 0.944 (+0.000) | 0.716 → 0.870 (+0.155) | 0.211 → 0.222 (+0.011) | 0.097 → 0.095 (-0.001) | 2812.889 → 3502.889 (+690.000) |
| bge-small | 0.611 → 0.611 (+0.000) | 0.722 → 0.944 (+0.222) | 0.861 → 0.944 (+0.083) | 0.833 → 0.944 (+0.111) | 0.696 → 0.759 (+0.063) | 0.189 → 0.211 (+0.022) | 0.091 → 0.095 (+0.004) | 2900.500 → 3463.278 (+562.778) |
| minilm-l6 | 0.417 → 0.667 (+0.250) | 0.750 → 0.944 (+0.194) | 0.861 → 1.000 (+0.139) | 0.833 → 1.000 (+0.167) | 0.598 → 0.794 (+0.196) | 0.200 → 0.233 (+0.033) | 0.092 → 0.085 (-0.007) | 2802.222 → 3309.944 (+507.722) |
| portfolio-e5-small | 0.528 → 0.861 (+0.333) | 0.806 → 0.944 (+0.139) | 0.889 → 0.972 (+0.083) | 0.833 → 0.944 (+0.111) | 0.657 → 0.910 (+0.253) | 0.200 → 0.222 (+0.022) | 0.094 → 0.090 (-0.003) | 2774.278 → 3215.778 (+441.500) |
| portfolio-gte-small | 0.556 → 0.667 (+0.111) | 0.806 → 0.944 (+0.139) | 0.861 → 0.944 (+0.083) | 0.833 → 0.944 (+0.111) | 0.662 → 0.782 (+0.120) | 0.189 → 0.211 (+0.022) | 0.094 → 0.091 (-0.003) | 2785.278 → 3345.611 (+560.333) |
| qwen3-embedding | 0.583 → 0.806 (+0.222) | 0.722 → 0.917 (+0.194) | 0.778 → 0.972 (+0.194) | 0.722 → 0.944 (+0.222) | 0.655 → 0.866 (+0.211) | 0.178 → 0.222 (+0.044) | 0.094 → 0.091 (-0.003) | 2694.333 → 3493.278 (+798.944) |

## Macro paired uncertainty

Embedding routes are averaged within each case before cases are resampled, so six correlated model outputs are not treated as six independent questions.

| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI | W/T/L | Exact sign p |
|---|---:|---:|---:|---:|---:|---:|
| Evidence recall@1 | 0.551 | 0.731 | +0.181 | [+0.037, +0.347] | 8/8/2 | 0.1094 |
| Evidence recall@3 | 0.759 | 0.944 | +0.185 | [+0.065, +0.333] | 8/10/0 | 0.0078 |
| Evidence recall@5 | 0.866 | 0.968 | +0.102 | [+0.019, +0.213] | 5/13/0 | 0.0625 |
| All-evidence success@5 | 0.833 | 0.954 | +0.120 | [+0.019, +0.250] | 4/14/0 | 0.1250 |
| Mean evidence reciprocal rank@5 | 0.664 | 0.830 | +0.166 | [+0.057, +0.296] | 9/7/2 | 0.0654 |
| Required-context precision@5 | 0.194 | 0.220 | +0.026 | [+0.004, +0.054] | 5/13/0 | 0.0625 |
| Context token-set redundancy@5 | 0.094 | 0.091 | -0.002 | [-0.007, +0.002] | 9/0/9 | 1.0000 |
| Context characters@5 | 2794.917 | 3388.463 | +593.546 | [+493.277, +694.316] | descriptive | — |

## Shared-fact cluster sensitivity

The 18 cases form **15 fact clusters**. Resampling those clusters keeps query variants about the same fact together.

| Metric | Delta | Case-bootstrap CI | Fact-cluster CI |
|---|---:|---:|---:|
| Evidence recall@1 | +0.181 | [+0.037, +0.347] | [+0.032, +0.359] |
| Evidence recall@3 | +0.185 | [+0.065, +0.333] | [+0.059, +0.338] |
| Evidence recall@5 | +0.102 | [+0.019, +0.213] | [+0.021, +0.221] |
| All-evidence success@5 | +0.120 | [+0.019, +0.250] | [+0.017, +0.267] |
| Mean evidence reciprocal rank@5 | +0.166 | [+0.057, +0.296] | [+0.051, +0.311] |
| Required-context precision@5 | +0.026 | [+0.004, +0.054] | [+0.005, +0.055] |
| Context token-set redundancy@5 | -0.002 | [-0.007, +0.002] | [-0.007, +0.002] |

## Fixed context-budget comparison

This controls the main Top-K confound: manual chunks are larger. Each row measures the production-formatted source excerpts, keeps the rank-preserving Top-5 prefix, and stops before adding a whole chunk that would exceed the budget.

| Budget | Evidence recall | All-evidence success | Actual chars (automatic → manual) | Chunks (automatic → manual) |
|---:|---:|---:|---:|---:|
| 1500 | 0.671 → 0.838 (+0.167) | 0.630 → 0.815 (+0.185) | 1180 → 1203 | 2.12 → 1.83 |
| 2000 | 0.764 → 0.884 (+0.120) | 0.722 → 0.861 (+0.139) | 1751 → 1680 | 3.13 → 2.52 |
| 2500 | 0.801 → 0.898 (+0.097) | 0.759 → 0.870 (+0.111) | 2219 → 2099 | 3.98 → 3.17 |

## Evidence-level regressions

- Coverage gains: **16**
- Coverage losses: **0**
- Rank improvements within Top 5: **36**
- Rank regressions within Top 5: **8**

## Metric definitions

- **R@K:** fraction of required evidence groups found by rank K.
- **All evidence@K:** fraction of questions for which every required evidence group is present by rank K.
- **Mean evidence RR@5:** reciprocal rank averaged across every evidence group, not only the first hit.
- **Required context P@5:** fraction of returned chunks matching required qrels; it is a lower bound because qrels do not label every merely useful chunk.
- **Redundancy@5:** mean pairwise Jaccard similarity between retrieved chunk token sets; lower means less repeated context.
- **Context chars@5:** production-formatted source-excerpt size; descriptive, not automatically better when smaller.
- **Fixed context budget:** evidence metrics after limiting production-formatted source excerpts to the same strict character ceiling; this separates boundary quality from simply returning more text.
