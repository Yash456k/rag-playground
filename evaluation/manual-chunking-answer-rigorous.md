# DeepSeek V4 Flash answer evaluation: automatic vs manual chunking

> Paired quality results include only requests completed by the requested model on both sides. Provider errors and fallbacks are reported separately and never scored as answer-quality losses.

## Sample

- Aligned pairs: **16**
- Quality-eligible pairs: **16**
- Provider/fallback exclusions: **0**

## Paired quality table

| Metric | Automatic → manual (delta) | 95% paired bootstrap CI | W/T/L |
|---|---:|---:|---:|
| Contract pass rate | 0.625 → 0.812 (+0.188) | [-0.062, +0.438] | 4/11/1 |
| Required-claim gate | 0.688 → 0.938 (+0.250) | [+0.062, +0.500] | 4/12/0 |
| Refusal gate | 0.938 → 0.938 (+0.000) | [-0.188, +0.188] | 1/14/1 |
| Forbidden-claim gate | 1.000 → 1.000 (+0.000) | [+0.000, +0.000] | 0/16/0 |
| Citation gate | 0.812 → 0.875 (+0.062) | [-0.125, +0.250] | 2/13/1 |
| Required claim-group coverage | 0.859 → 0.962 (+0.103) | [+0.000, +0.218] | 3/10/0 |
| Retrieved evidence-group coverage@3 | 0.923 → 1.000 (+0.077) | [+0.000, +0.192] | 2/11/0 |
| Cited evidence-group coverage | 0.923 → 1.000 (+0.077) | [+0.000, +0.192] | 2/11/0 |
| Valid citation references | 1.000 → 1.000 (+0.000) | [+0.000, +0.000] | 0/16/0 |
| Total latency (ms) | 5814.281 → 9460.250 (+3645.969) | [-1491.752, +8535.621] | descriptive |
| Total tokens | 974.375 → 1059.062 (+84.688) | [+11.248, +165.189] | descriptive |
| Reported provider cost (USD) | 0.000 → 0.000 (+0.000) | [-0.000, +0.000] | descriptive |

## Contract pass changes

- Pass gains: **4**
- Pass losses: **1**
