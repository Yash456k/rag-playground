# Portfolio embedder training

This pipeline performs genuine full-model fine-tuning, one CUDA model at a time:

- `intfloat/e5-small-v2` at revision
  `ffb93f3bd4047442299a41ebb6fa998a38507c52` uses
  `MultipleNegativesRankingLoss` with a no-duplicates sampler and the
  required `query: ` / `passage: ` prefixes.
- `thenlper/gte-small` at revision
  `17e1f347d17fe144873b1201da91788898c639cd` uses
  `MultipleNegativesRankingLoss`, the no-duplicates sampler, and explicit reviewed
  hard negatives.

E5 omits explicit negatives because its required query/passage representation was
more stable with in-batch negatives alone. GTE benefits from the reviewed hard
negatives. The release gates emphasize Recall@5 because production supplies five
passages to generation, while Recall@1, Recall@3, and MRR still enforce useful order.

Install and validate without downloading a model or requiring a GPU:

```bash
python -m pip install -r requirements-train.txt
python scripts/train_portfolio_embedders.py --validate-only
```

Run both recipes sequentially on CUDA:

```bash
python scripts/train_portfolio_embedders.py
```

The accepted exports are `model-artifacts/portfolio-e5-small-v1` and
`model-artifacts/portfolio-gte-small-v1`. A candidate is promoted to those paths only
after it contains safetensors weights, its trained state checksum differs from the
base state, it executed optimizer steps, and it passes every DEV retrieval gate.
Existing accepted artifacts are preserved unless `--overwrite` is explicitly passed.

Each artifact's `training-manifest.json` records the pinned base, seed,
hyperparameters, optimizer steps, software versions, dataset/corpus hashes, base and
trained state hashes, pre/post DEV metrics with per-question ranks, acceptance checks,
and checksums for every exported file. The locked holdout hash is recorded as evidence
of split identity, but its questions are never encoded or scored by this trainer.

After reviewing both manifests, transfer without recompressing model files:

```bash
rsync -a --checksum --info=progress2 model-artifacts/portfolio-e5-small-v1/ \
  hermes-hetzner:/opt/rag-playground/model-artifacts/portfolio-e5-small-v1/
rsync -a --checksum --info=progress2 model-artifacts/portfolio-gte-small-v1/ \
  hermes-hetzner:/opt/rag-playground/model-artifacts/portfolio-gte-small-v1/
```
