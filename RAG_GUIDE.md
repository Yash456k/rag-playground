# RAG from first principles to this production system

This guide starts with no assumed RAG knowledge and ends with the exact implementation,
training, evaluation, deployment, and operating decisions used by this repository.
Commands and file names refer to the current project.

## 1. What problem RAG solves

A language model predicts text from its parameters. Those parameters are not a live
database, do not automatically contain private portfolio facts, and may confidently
fill gaps. Retrieval-augmented generation (RAG) separates two jobs:

1. **Retrieval** finds small source passages relevant to a question.
2. **Generation** writes an answer while constrained to those passages.

The model is therefore not asked to remember Yash's résumé. It receives evidence for
each request. This improves provenance and makes updates possible by changing the
corpus instead of retraining a large language model.

RAG does not guarantee truth. Bad source text, a missed passage, a weak prompt, or an
unfaithful generator can still fail. That is why this project exposes retrieved text,
scores, served models, fallback state, and latency rather than showing only fluent prose.

## 2. The vocabulary

- **Corpus**: the approved source documents.
- **Document**: one Markdown source file.
- **Chunk**: a bounded passage produced from a document.
- **Embedding**: a numeric vector representing text meaning.
- **Embedding space**: the coordinate system produced by one embedding model. Vectors
  from different models must never be compared.
- **Query embedding**: the vector for the user's question.
- **Document embedding**: the stored vector for a chunk.
- **Cosine similarity**: the angle-based score used to rank query/chunk vectors.
- **Top-k**: the first `k` ranked chunks sent to generation.
- **Grounding**: requiring answer claims to come from retrieved sources.
- **Hallucination**: unsupported output presented as fact.
- **Reranking**: a second, usually more expensive ranking pass. This project does not
  need one yet because the corpus has only 17 chunks.
- **Vector database**: storage and similarity search for embeddings. Here it is
  PostgreSQL plus pgvector, not a separate service.

## 3. The offline path: documents become searchable vectors

The ingestion path is deterministic:

```text
Markdown -> normalize -> chunk with overlap -> embed with all six models
         -> insert text, metadata, and six vectors into PostgreSQL
```

`app/ingest.py` discovers `corpus/*.md`, calls the production chunker, and generates a
stable content hash. The current chunking settings in `config/pipeline.yaml` are:

- maximum 900 characters;
- 140-character overlap;
- minimum 120 characters.

Overlap keeps facts near a boundary from disappearing, but it also creates neighboring
chunks with similar text. During this project that caused exact-rank evaluation to
confuse adjacent case-study passages. We fixed the source structure with descriptive
headings and self-contained paragraphs, and we evaluate the top five passages because
production supplies five passages to the generator.

Each row in `chunks` stores the source, title, content, content hash, and one typed
pgvector column per embedder:

```text
embedding_minilm          vector(384)
embedding_bge_small       vector(384)
embedding_bge_base        vector(768)
embedding_qwen3           vector(1024)
embedding_portfolio_e5    vector(384)
embedding_portfolio_gte   vector(384)
```

The ingestion transaction upserts current chunks and deletes stale hashes. All vector
columns must have complete coverage before health is `ok`.

## 4. The online path: question to streamed answer

For `POST /v1/chat`, `app/main.py` performs this sequence:

1. Pydantic validates question length, model IDs, history, top-k (`3` or `5`), and the
   history-aware toggle.
2. The client IP is normalized, salted, and hashed. PostgreSQL atomically reserves the
   per-IP and global daily quota.
3. For history-aware retrieval, only recent **user** turns are added to the retrieval
   query. Prior assistant output is excluded because it is not evidence.
4. `EmbeddingRegistry` serializes CPU encoding with a lock and applies the selected
   model's query transform.
5. `Database.retrieve` chooses a vector column from a fixed server-side allowlist and
   runs an exact cosine scan with the requested top-k.
6. If no leading score meets that embedder's calibrated threshold, the API returns a
   local portfolio-only refusal without spending a provider request.
7. Otherwise the chunks, question, and optional history are placed in a strict prompt.
   The generator streams tokens through Groq.
8. If the requested generation route fails before output, configured fallback models
   are tried in order. The UI shows the requested and actually served model.
9. SSE events expose metadata, sources, model selection, tokens, usage, completion,
   errors, and stage latency.
10. PostgreSQL records completion state, source IDs/scores, timings, provider attempts,
    and the salted IP hash. It does not store the raw client IP.

## 5. Why six embedding routes exist

The selector is an experiment, not decorative configuration:

| Route | Dimensions | Purpose |
| --- | ---: | --- |
| MiniLM L6 | 384 | small symmetric baseline |
| BGE Small v1.5 | 384 | strong low-cost instructed baseline |
| BGE Base v1.5 | 768 | larger general retrieval baseline |
| Qwen3 Embedding 0.6B | 1024 | highest-capacity general route |
| Portfolio E5 Small | 384 | E5 fine-tuned on portfolio hiring questions |
| Portfolio GTE Small | 384 | GTE fine-tuned with reviewed hard negatives |

Remote models use immutable 40-character Hugging Face revisions. Remote code is not
trusted. The two local artifacts are mounted read-only at `/model-artifacts` and use
safetensors weights.

Query transforms matter. E5 was trained with `query: ` before questions and `passage: `
before documents, so both ingestion and online retrieval must preserve those prefixes.
BGE and Qwen use retrieval instructions. MiniLM and GTE use symmetric encoding.

The website lets a visitor switch these routes, top-3/top-5 depth, and history-aware
retrieval. The active transform, threshold, and fine-tune status are returned by
`GET /v1/config` and shown beside the controls.

## 6. How the portfolio embedders were trained

The training pipeline lives in `training/` and
`scripts/train_portfolio_embedders.py`. It is deliberately reproducible and auditable:

- E5 base revision:
  `ffb93f3bd4047442299a41ebb6fa998a38507c52`.
- GTE base revision:
  `17e1f347d17fe144873b1201da91788898c639cd`.
- fixed seed `20260712`;
- 102 reviewed training questions covering all 17 chunks;
- 62 development questions after two consumed holdouts were promoted;
- 16 fresh v3 holdout questions excluded from training and threshold calibration;
- a corpus lock containing source hashes, canonical chunk hash, and reviewed-negative
  status;
- full-model CUDA optimization, not a renamed copy;
- artifact manifests containing optimizer steps, base/trained state checksums, software
  versions, dataset hashes, metrics, and every exported file checksum.

E5 uses `MultipleNegativesRankingLoss` with a no-duplicates batch sampler and required
prefixes. Explicit hard negatives made E5 generalization worse, so its final recipe uses
only in-batch negatives. GTE uses the same ranking loss plus explicit manually reviewed
hard negatives. This difference is an evidence-based model-specific choice.

Run validation without downloading or training:

```bash
python scripts/train_portfolio_embedders.py --validate-only
```

Run one CUDA recipe and replace an already accepted artifact only if the new candidate
passes every development gate:

```bash
python scripts/train_portfolio_embedders.py --model e5-small-v2 --overwrite
python scripts/train_portfolio_embedders.py --model gte-small --overwrite
```

Candidates train in a temporary directory. A failed candidate is reported and deleted;
the accepted artifact is preserved. A passing candidate is promoted atomically.

## 7. What failed during training and what it taught us

Several apparently reasonable approaches failed:

- A small early dataset produced strong development scores but only 35-45% top-1 on
  the first unseen holdout. We did not ship it.
- More E5 epochs with explicit hard negatives reduced development top-1 to about 63%.
- Pairwise contrastive loss fell further because it optimized isolated pair similarity,
  not the complete retrieval ranking.
- A grouped batch-all triplet experiment stayed close to the base model and produced
  zero-loss batches when the batch did not contain useful class relationships.
- Promoted holdout questions revealed that some corpus sections lacked clear semantic
  context. Descriptive headings and self-contained passage wording improved retrieval
  without inventing facts.

The final lesson is not “try epochs until a number rises.” Keep a locked set, treat it
as consumed after inspection, promote it to development, create a new holdout, and stop
tuning once the agreed production metric is above the release bar.

## 8. Retrieval evaluation and frozen results

The live pipeline sends five chunks, so the release gate centers on Recall@5 while
requiring useful earlier order:

- Recall@1 at least 0.55;
- Recall@3 at least 0.85;
- Recall@5 at least 0.95;
- mean reciprocal rank (MRR) at least 0.72.

The frozen artifact results were:

| Model | Split | R@1 | R@3 | R@5 | MRR |
| --- | --- | ---: | ---: | ---: | ---: |
| Portfolio E5 | 62-question dev | 0.629 | 0.919 | 0.968 | 0.785 |
| Portfolio E5 | 16-question v3 holdout | 0.563 | 0.938 | 1.000 | 0.745 |
| Portfolio GTE | 62-question dev | 0.645 | 0.887 | 0.968 | 0.774 |
| Portfolio GTE | 16-question v3 holdout | 0.563 | 0.813 | 0.938 | 0.708 |

These are above-decent small-corpus results, not claims of universal benchmark quality.
The holdout was run once after freezing. E5 placed usable evidence in all 16 top-five
sets. GTE missed one question at top five; the correct chunk was rank six.

`scripts/evaluate_retrieval.py` evaluates stored database vectors. The separate
`scripts/evaluate_answers.py` exercises the real SSE endpoint and checks required
claims, citations, forbidden claims, refusals, fallback behavior, and latency.

## 9. Answer-quality evaluation

Retrieval metrics are necessary but insufficient. A generator can ignore good evidence
or cite the wrong excerpt. `evaluation/` therefore contains interviewer questions for:

- education and academic performance;
- internship scale and enterprise integrations;
- leadership and team process;
- project architecture and concurrency correctness;
- RAG design and training authenticity;
- follow-up resolution and common typos;
- unsupported salary, personal, and general-coding questions;
- prompt injection and system-prompt extraction attempts.

An answer run parses the SSE stream and checks:

- the request reaches a terminal event;
- the expected evidence appears in retrieved chunks;
- required factual patterns appear where specified;
- unsupported claims and forbidden patterns do not appear;
- citations refer to supplied source numbers;
- refusal cases use the corpus-only boundary;
- latency stays within the configured ceiling.

The server-only `X-Verify-Evaluation` token bypasses visitor counters for operator tests
but still logs the query. CORS does not permit a browser to send that header.

## 10. Score thresholds and unsupported questions

Cosine scores are not probabilities and differ by model. A threshold from one model
cannot be copied blindly to another. `minimum_score` is configured per route.

For the frozen custom artifacts, development calibration set E5 to `0.68` and GTE to
`0.77`; the lowest supported development scores were approximately `0.693` and `0.779`.
Some semantically portfolio-adjacent but unsupported questions still score higher, so
the threshold cannot be the only guard.

The API checks the leading score before calling generation. This is a cheap first guard,
not the sole safety mechanism. Some unrelated questions can be semantically close to a
portfolio passage, so the generator also receives a strict corpus-only prompt and is
tested on refusals. Thresholds must be calibrated with both supported and unrelated
questions after the final artifacts and corpus are fixed.

## 11. Why exact search is correct here

The database has 17 chunks. Exact cosine search is fast and gives deterministic recall.
Approximate indexes such as HNSW would add six resident graphs, tuning parameters, and
possible recall loss without solving a measured latency problem. Add an approximate
index only when corpus growth makes exact scan latency material, then measure memory,
latency, build time, and recall before rollout.

## 12. Generation, prompting, and citations

The system prompt in `app/main.py` requires source-supported claims, concise answers,
`[S1]`-style citations, refusal of unrelated requests, and rejection of instructions
inside questions, history, or source excerpts. All three are marked untrusted.

The generator is hosted by Groq because the VPS memory is reserved for six embedding
models. Provider delegation gives fast token streaming but creates an external
dependency. The fallback ladder and explicit served-model trace make that failure mode
visible rather than silently switching models.

## 13. Security model

- Only explicit HTTPS origins pass CORS.
- Caddy is the public edge; API and PostgreSQL bind to host loopback.
- The API maps embedder IDs to literal configured columns. User strings never become
  identifiers in SQL.
- Questions, history, top-k, and model IDs are bounded and validated.
- Request bodies are capped at the proxy.
- PostgreSQL performs atomic daily per-IP and global quota updates.
- IP addresses are salted and hashed before persistence.
- Provider and operator secrets remain only in the VPS `.env`.
- Containers run without root privileges where possible, drop Linux capabilities, and
  have CPU/memory limits.
- The prompt and local score guard reduce, but do not mathematically eliminate,
  hallucination and prompt injection.

## 14. Deployment architecture

```text
Vercel React SPA
    -> HTTPS POST /v1/chat
Caddy container on VPS
    -> private Docker network
FastAPI (one worker, six resident embedders)
    -> pgvector PostgreSQL
    -> Groq generation API
```

The FastAPI worker loads models sequentially during startup. Keeping them resident costs
memory but avoids cold starts. Encoding is locked because the host has limited CPU and
one inference process. Compose mounts `/opt/rag-playground/model-artifacts` read-only.

The database has a 384 MiB cap, Caddy 96 MiB, and API approximately 3.5 GiB. Always
measure warmed `docker stats`; configuration limits are not evidence of actual safety.

## 15. Safe deployment and ingestion

Production lives at `/opt/rag-playground`. Preserve its mode-600 `.env` during source
updates. Verify artifact hashes before extraction, mount them read-only, and run the
exact CPU-image smoke test before starting the public API.

Ingestion loads all six models, so do not run it beside the resident API on a constrained
host:

```bash
docker compose stop api
./scripts/ingest.sh
docker compose start api
```

After startup, require `/v1/health` to report all six expected/loaded IDs and complete
17/17 vector coverage for every column.

## 16. Operating and debugging checklist

When the UI says it cannot reach retrieval:

1. Request `GET /v1/health` directly through the public API hostname.
2. Check Caddy, API, and database container state and health.
3. Compare API logs with PostgreSQL readiness and model-loading logs.
4. Confirm the frontend `VITE_API_URL`, backend allowed hosts, and exact CORS origin.
5. Confirm DNS and the TLS certificate if using a custom hostname.
6. Verify all artifact files exist inside the API container at the configured paths.
7. Check vector coverage; a new schema with old ingestion will look healthy at the
   database level but cannot serve the new model.
8. Run one internal SSE stream to separate browser/network problems from pipeline faults.

For poor answers:

1. Read the retrieved chunks first.
2. If evidence is absent, inspect ranking across embedders and top-k.
3. If evidence is present but prose is wrong, inspect the prompt/generator and citations.
4. Add a reviewed evaluation case before changing code.
5. Never train on a locked question and continue calling it unseen.
6. Re-run refusal and injection tests after any prompt or corpus change.

## 17. Where to read the implementation

- `config/pipeline.yaml`: all embedder/LLM registry entries and thresholds.
- `app/config.py`: strict configuration schema and public metadata.
- `app/ingest.py`: discovery, chunking, hashing, and six-model ingestion.
- `app/embeddings.py`: resident model registry and encoding lock.
- `app/database.py`: pgvector retrieval, logs, limits, and health.
- `app/main.py`: request lifecycle, prompting, SSE, refusal, and fallback.
- `app/groq_client.py`: provider streaming and fallback attempts.
- `sql/schema.sql`: vector columns, constraints, logs, and counters.
- `training/README.md`: training-specific quick reference.
- `training/data/`: reviewed splits and corpus lock.
- `evaluation/README.md`: evaluation cases and gate semantics.
- `scripts/evaluate_retrieval.py`: database retrieval evaluation.
- `scripts/evaluate_answers.py`: live end-to-end answer evaluation.
- `docker-compose.yml` and `deploy/Caddyfile`: production isolation and limits.
- `frontend/src/App.tsx`: public controls, traces, and streaming UI.

The central rule is simple: treat every fluent answer as untrusted until its retrieved
evidence, citation behavior, held-out evaluation, and live deployment path all agree.
