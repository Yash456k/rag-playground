# RAG Playground progress

Last updated: 2026-07-11 22:36 IST

## Goal

Ship a public portfolio RAG playground with a Vite/React frontend on Vercel and an isolated FastAPI + pgvector stack under `/opt/rag-playground` on `hermes-hetzner`.

## Safety boundaries

- Do not modify SSH, fail2ban, UFW SSH rules, Tailscale, or existing containers.
- New Docker resources use the `rag-playground` Compose project and explicit names.
- Postgres binds only to `127.0.0.1:55432`; the API binds only to `127.0.0.1:18080`.
- API + database + proxy memory limits will stay below 4.5 GiB; actual residency must be verified with `docker stats` after all four embedders are warm.
- Secrets belong only in the VPS `.env` and Vercel environment, never Git.

## Current status

- [x] Confirmed SSH access to `hermes-hetzner` as `yash`.
- [x] Recorded the VPS baseline: 4 vCPU, 7.6 GiB RAM/no swap, 4.8 GiB available, no pre-existing Docker runtime, and host-native services on loopback ports 5432/8000/8880/8642/8643.
- [ ] Resolve audit deviation: an Ubuntu `lxc` installer wrapper unexpectedly installed and started the LXD snap during an intended read-only probe. Passive inspection found no `lxdbr0` interface or LXD IP address; no rollback has been attempted.
- [x] Reconciled real public details from the tracked resume and both portfolio source trees without modifying either portfolio repository.
- [x] Added two truthful starter corpus documents with RAG Playground first, corrected contact/project links, and dated work history.
- [x] Implemented the backend, frontend, isolated Compose/Caddy assets, ingestion, retention, and automated tests.
- [x] Verified 34 backend tests, 2 frontend parser tests, Ruff, ESLint, TypeScript, and the Vite production build.
- [x] Built the exact CPU Docker image locally. Four-model smoke: 1,943.3 MiB RSS with all models resident; query latency was 8.1/17.2/61.2/527.1 ms for MiniLM/BGE Small/BGE Base/Qwen3 under a 2.5 CPU / 4 GiB container cap.
- [ ] Create and push a new GitHub repository.
- [ ] Deploy the isolated VPS stack and ingest the corpus.
- [ ] Configure an HTTPS API subdomain and strict frontend CORS.
- [ ] Deploy the frontend to Vercel production.
- [ ] Run the final live verification matrix with captured outputs.

## Architecture decisions

- One API process loads all four embedding models during startup and keeps them resident.
- One `chunks` row has four separate pgvector columns; selection maps through a fixed server-side column allowlist.
- Exact cosine scans are used for the resume-sized corpus to preserve recall and avoid four resident HNSW graphs.
- Retrieval and model metadata are driven by `config/pipeline.yaml` and exposed read-only at `/v1/config`.
- Groq streaming is proxied as SSE. The requested model is tried first, then configured fallbacks; the final event records the actual model and fallback path.
- Daily rate limits use atomic PostgreSQL counters for both a salted IP hash and a global bucket.
- Query logs store the question, selections, actual model, retrieval/latency metadata, and salted IP hash.

## Resume point

Continue from the first unchecked item. Before any VPS mutation, compare the current Docker/service state against the audit baseline. Update this file after every deployment milestone and log any deviation rather than silently reducing scope.
