# Portfolio RAG Eval V2 — expanded embedder study

**Run:** 2026-07-29 19:03 IST
**Execution host:** `yash456k-GF63-Thin-9SCSR`
**GPU:** NVIDIA GeForce GTX 1650 Ti Max-Q, 4 GiB
**Code commit:** `d3ba86f27cc0c53258474acc85bb73306f62e9be`
**Live production default:** `bge-small`
**First-wave winner:** `minilm-l6`

## Conclusion

The expanded search did **not** find a better deployment choice than MiniLM L6.

Snowflake Arctic Embed M V2 narrowly led MiniLM on challenge nDCG@5 by **0.0012**, but trailed it by **0.0467** on development nDCG@5, had lower Recall@5 on both splits, was **2.96× slower**, and used **8.51× more GPU memory**. The challenge confidence intervals overlap heavily, and this challenge has already been inspected, so the 0.0012 difference is not actionable evidence.

**Recommendation remains:** replace the live `bge-small` default with `minilm-l6` in a separate controlled production change. No production configuration was changed by this study.

## Fixed benchmark protocol

- Database-free exact cosine retrieval over the same 22 production-derived chunks.
- Same 120 cases, 40 intent families, qrels, query rewriting, diversity pass, and top-K settings as the original Eval V2 run.
- Development and challenge are reported separately; pooled views remain informational only.
- CUDA, one model at a time, three warm-ups, three timed query encodes, top-K 5.
- Family-cluster bootstrap: 2,000 samples, seed 1729.
- Every Hugging Face model is pinned to an immutable 40-character revision.
- Candidate-specific SentenceTransformers prompt names were used where required.
- Full run wall time: **108.81 seconds**.
- Maximum process RSS: **3,293,704 KiB / 3.14 GiB**.
- All seven models in the final comparison completed successfully.

## Final comparison

| Model | Role | Dev nDCG@5 | Challenge nDCG@5 | Dev Recall@5 | Challenge Recall@5 | Mean latency | QPS | Peak VRAM |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **MiniLM L6** | First-wave winner | **0.8235** | 0.7837 | 0.9375 | **0.9500** | **4.509 ms** | **221.2** | **158.4 MiB** |
| Arctic Embed M V2 | Challenger | 0.7768 | **0.7849** | 0.8750 | 0.9000 | 13.333 ms | 74.9 | 1,347.8 MiB |
| GTE ModernBERT Base | Challenger | 0.7484 | 0.6717 | **0.9444** | 0.8333 | 19.808 ms | 50.5 | 350.6 MiB |
| Harrier OSS 270M | Challenger | 0.7235 | 0.7268 | 0.8958 | 0.8667 | 24.211 ms | 41.3 | 1,150.5 MiB |
| LFM2.5 Embedding 350M | Challenger | 0.7171 | 0.6850 | 0.8333 | 0.9000 | 33.713 ms | 29.7 | 855.9 MiB |
| Mixedbread Embed Large V1 | Challenger | 0.6937 | 0.7799 | 0.8194 | 0.9333 | 55.966 ms | 17.9 | 730.8 MiB |
| **BGE Small** | Live default | 0.6878 | 0.6713 | 0.8125 | 0.8667 | 7.543 ms | 132.4 | 199.2 MiB |

### Direct interpretation

- **MiniLM vs BGE Small:** +0.1357/+0.1123 development/challenge nDCG@5, 40.2% lower latency, and 20.5% lower peak allocated VRAM.
- **MiniLM vs Arctic:** +0.0467 development nDCG@5 and -0.0012 challenge nDCG@5. MiniLM still had +0.0625/+0.0500 development/challenge Recall@5.
- **MiniLM vs Mixedbread:** nearly tied on challenge quality, but MiniLM was much stronger on development and roughly twelve times faster.
- **GTE ModernBERT:** excellent development Recall@5, but its challenge quality and recall dropped sharply. It does not generalize reliably enough here.
- **LFM2.5:** ran successfully and fit the hardware, but did not justify its latency or memory cost.
- **Harrier:** required float32 on the GTX 1650 Ti. Its native bfloat16-to-float16 fallback produced non-finite vectors; the evaluator was hardened to reject NaN, infinity, and zero-norm embeddings before ranking.

## Pairwise MiniLM evidence

At the answerable-query level, MiniLM's mean nDCG@5 delta against Arctic was +0.0467 on development and -0.0012 on challenge. Challenge W/T/L was 11/10/9 for MiniLM, while Recall@5 was 2/27/1 with a +0.0500 mean delta. The nDCG confidence intervals overlap:

- MiniLM development: **[0.7536, 0.8891]**
- Arctic development: **[0.6890, 0.8591]**
- MiniLM challenge: **[0.6968, 0.8666]**
- Arctic challenge: **[0.6966, 0.8742]**

This is evidence that Arctic is competitive, not evidence that it is superior.

## Search coverage and model-specific outcomes

Eleven additional retrieval-ready models were researched from first-party model cards and Hugging Face API metadata. Five produced valid full Eval V2 results.

| Candidate | Parameters | License | Outcome |
|---|---:|---|---|
| GTE ModernBERT Base | 149M | Apache-2.0 | Full benchmark completed |
| Mixedbread Embed Large V1 | 335M | Apache-2.0 | Full benchmark completed |
| Snowflake Arctic Embed M V2 | 305M | Apache-2.0 | Full benchmark completed after installing pinned xformers |
| LFM2.5 Embedding 350M | 354M | LFM Open License 1.0 | Full benchmark completed |
| Microsoft Harrier OSS 270M | 268M | MIT | Full benchmark completed in float32 |
| Nomic Embed Text V2 MoE | 475M total / 305M active | Apache-2.0 | Operational smoke timed out after more than 10 minutes without Megablocks; consumed about 2 GiB swap, so it is not practical in this pinned environment |
| EmbeddingGemma 300M | 303M | Gemma | HTTP 401: manual model-license access was not granted to the old laptop account |
| Perplexity Embed V1 0.6B | 596M | MIT | Size-screened after the download probe; no valid quality result claimed |
| BGE M3 | 568M | MIT | Screened out of the compact full run because Arctic is smaller and its own card reports stronger English BEIR performance |
| Stella EN 400M V5 | 435M | MIT | Screened out of the compact full run due larger custom-code/runtime footprint |
| Jina V5 Nano Retrieval | 212M | CC-BY-NC-4.0 | Not a deployment candidate: non-commercial license and runtime requirements exceed the pinned Transformers/SentenceTransformers stack |

No score is invented for models that did not complete valid end-to-end encoding.

## Runtime findings

- Arctic requires `trust_remote_code=True` and xformers. `xformers==0.0.31` was pinned to the existing torch 2.7.1/cu126 stack.
- Nomic requires `einops`; its first-party card recommends Nomic's Megablocks fork for acceptable GPU speed. The pure-PyTorch path was not operationally acceptable on this laptop.
- LFM2.5 was authored with SentenceTransformers 5.1.1 while the repository pins 5.1.0. It completed, but that warning must be resolved before deployment consideration.
- The evaluator now validates shape, finiteness, and vector norm before ranking. This prevents numerically invalid embeddings from appearing as plausible quality scores.

## Threshold and generalization warning

None of the benchmark-only challengers has a production similarity threshold. Their configured-threshold sections are therefore marked unavailable; only development-calibrated diagnostics are shown.

Threshold transfer remains weak for all serious candidates. Encoder replacement should not be presented as a refusal/answerability fix. Build a larger negative suite and calibrate the chosen encoder separately.

The current challenge was inspected during the first-wave analysis and is now regression data. A fresh locked challenge set is required before claiming a small future improvement over MiniLM.

## Decision

1. Keep **MiniLM L6** as the promotion candidate.
2. Do not promote Arctic: its tiny challenge nDCG edge does not survive the development, recall, latency, memory, and uncertainty trade-offs.
3. Do not change similarity thresholds in the encoder switch.
4. Do not change production automatically from this branch.
