# RAG Playground engineering case study

## Product goal and inspectability

Yash built RAG Playground as a public portfolio question-answering system whose behavior can be inspected rather than treated as a black box. The browser lets a visitor choose an embedding model and a Groq-hosted generation model. Each streamed answer exposes the retrieved chunks, cosine-similarity scores, requested and served models, fallback state, and embedding, retrieval, first-token, generation, and total latency.

The system is deliberately limited to a curated portfolio corpus. Its prompt treats the question, conversation history, and retrieved text as untrusted data, requires claims to be supported by supplied excerpts, and refuses unrelated or unsupported requests. PostgreSQL records query selections, retrieved source identifiers and scores, provider attempts, completion state, and stage latency without storing raw client IP addresses.

## Retrieval architecture and model training

The production selector compares six resident 384-to-1024-dimensional embedding routes. Four are pinned general-purpose models: MiniLM L6, BGE Small v1.5, BGE Base v1.5, and Qwen3 Embedding 0.6B. Two additional 384-dimensional models are fine-tuned for portfolio and hiring questions from pinned E5 Small v2 and GTE Small bases. Training uses reviewed question-to-passage examples, hard negatives, deterministic seeds, and a separate evaluation set; locked interviewer questions are excluded from optimization and threshold calibration.

Every corpus chunk stores a separate pgvector column for each embedding space. The API maps a validated model identifier to a fixed server-side column allowlist, so visitor input never becomes an SQL identifier. E5 receives its required `query:` and `passage:` prefixes, while the other routes use their own configured query instructions.

Exact cosine scans are intentional for this small corpus. They preserve exact recall, avoid keeping six approximate-nearest-neighbor indexes in memory, and make model comparisons easier to interpret. The tradeoff is that exact scans scale linearly with corpus size; an approximate index should be considered only after the corpus grows enough for measured query latency to justify its memory and recall costs.

## Runtime and deployment tradeoffs

The service fits all six retrieval models onto modest VPS infrastructure. One FastAPI worker loads the embedding models sequentially during startup and keeps them resident. This uses more memory than loading a model per request, but avoids repeated cold starts and makes latency comparisons predictable. Encoding is serialized with a lock because the deployment has limited CPU and one inference process. The API container is capped at 2.5 CPU cores and 3,500 MiB; PostgreSQL is capped at 384 MiB and Caddy at 96 MiB.

The API and pgvector database bind only to host loopback addresses. A small Caddy container is the public HTTPS edge and reverse-proxies streaming responses to the private API. This isolation avoids exposing PostgreSQL or the application debug port. The Vite and React TypeScript frontend contains only the public API URL; the Groq key and operator verification token remain on the server.

Generation is delegated to Groq instead of running a large language model on the small VPS. That keeps local memory available for the embedding comparison and makes token streaming fast, but introduces a remote-provider dependency. The backend therefore tries configured fallback models, records every attempt, and reports the model that actually served the answer.

## Reliability, abuse controls, and verification

PostgreSQL atomically enforces a salted per-IP daily limit and a global daily limit. CORS accepts only explicit HTTPS frontend origins. Questions and history have strict size limits, Caddy caps request bodies, containers drop Linux capabilities, and production secrets are excluded from Git and Vercel's browser bundle.

The deployment is tested at several levels: unit and parser tests, deterministic retrieval evaluation, model-artifact checksum and compatibility checks, live SSE validation, prompt-injection and unsupported-question refusal checks, forced provider fallback, rate-limit enforcement, query-log verification, and warmed container memory measurements. Fine-tuned models must beat or match explicit retrieval gates on unseen hiring questions before they are exposed in the selector; a renamed but untrained base model is not accepted.
