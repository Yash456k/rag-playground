# RAG Playground progress

Last updated: 2026-07-12 14:12 IST

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
- [x] Resolved audit deviation: an Ubuntu `lxc` installer wrapper unexpectedly installed LXD. After confirming zero bridges, addresses, containers, VMs, storage pools, or networks, the snap was purged and the pre-audit interface state restored.
- [x] Reconciled real public details from the tracked resume and both portfolio source trees without modifying either portfolio repository.
- [x] Added two truthful starter corpus documents with RAG Playground first, corrected contact/project links, and dated work history.
- [x] Implemented the backend, frontend, isolated Compose/Caddy assets, ingestion, retention, and automated tests.
- [x] Verified 34 backend tests, 2 frontend parser tests, Ruff, ESLint, TypeScript, and the Vite production build.
- [x] Built the exact CPU Docker image locally. Four-model smoke: 1,943.3 MiB RSS with all models resident; query latency was 8.1/17.2/61.2/527.1 ms for MiniLM/BGE Small/BGE Base/Qwen3 under a 2.5 CPU / 4 GiB container cap.
- [x] Created and pushed the public repository at `https://github.com/Yash456k/rag-playground`.
- [x] Installed Ubuntu's `docker.io` and `docker-compose-v2` packages because the audited VPS had no container runtime. No pre-existing Docker containers existed.
- [x] Deployed the private API/database under `/opt/rag-playground`; ingestion produced 2 documents / 9 chunks with all 9 rows populated in each vector column.
- [x] Started the isolated Caddy proxy with the temporary `178-104-56-243.sslip.io` hostname, obtained a Let's Encrypt certificate, and validated public HTTPS without exposing the API's loopback port.
- [ ] Cut the public API hostname from the temporary fallback to `rag-api.yashx.me` after its DNS record exists.
- [x] Verified strict CORS: the Vercel production origin is echoed and an unlisted origin receives no allow-origin header.
- [x] Deployed Vercel production at `https://rag-playground-alpha.vercel.app`; custom domain `rag.yashx.me` is attached and waiting for DNS.
- [x] Connected the Vercel project to `Yash456k/rag-playground`, set production branch `main` and monorepo root `frontend`, and configured `VITE_API_URL` for production, preview, and development.
- [ ] Run the final live verification matrix with captured outputs.

## Current deployment evidence

- API loopback health is `ok`; database reports 9 chunks and vector coverage of 9/9 for all four embedders.
- After warmed queries across every embedder, `docker stats` reported API 510.8 MiB and Postgres 35.57 MiB. Both are well below the 4.5 GiB combined budget; proxy is capped at 96 MiB.
- Internal SSE checks passed for all 4 embedders and all 3 Groq models. Every stream emitted `meta`, `sources`, many `token` events, and `done` with per-stage latency.
- Off-topic prompt-injection questions were refused for all four embedders.
- Forced provider failure returned Groq 404 for the injected invalid model, then completed on GPT-OSS 20B with `fallbackUsed=true` and a logged attempt.
- The live PostgreSQL per-IP daily limiter returned HTTP 429 with `ip_daily_rate_limit_exceeded`.
- Existing SSH, fail2ban, Tailscale, PostgreSQL, Life Task API, OmniVoice, and Hermes listeners remain active with the same processes/listeners; UFW rules are unchanged.
- A real Brave session loaded `PIPELINE ONLINE` from the stable Vercel URL and completed a public BGE Small + GPT-OSS 20B stream with five visible sources. The trace reported 34 ms embedding, 5 ms retrieval, 504 ms first token, and 689 ms total latency.
- The matching PostgreSQL query log is `completed` with 824 answer characters and no fallback. After that request, API/database/proxy residency was 662.6/35.4/53 MiB.

## External DNS blocker

The application is operational through `https://178-104-56-243.sslip.io`, but the branded hostnames still need these records at the current `yashx.me` DNS provider:

- `A rag-api 178.104.56.243`
- `A rag 76.76.21.21`

After propagation, change the VPS `API_DOMAIN`, `PUBLIC_API_URL`, and `ALLOWED_HOSTS` back to the branded API hostname, recreate API/proxy, restore Vercel `VITE_API_URL`, and redeploy. Then run the remaining public verification matrix and rotate the exposed Groq key.

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
