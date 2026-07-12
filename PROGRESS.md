# RAG Playground deployment record

Last updated: 2026-07-12 17:15 IST

## Goal status

The public portfolio RAG is deployed and interactable at
`https://rag-playground-alpha.vercel.app`. Its API is currently served through the
temporary valid-TLS hostname `https://178-104-56-243.sslip.io` until the owner adds the
optional branded DNS records.

- [x] Six selectable embedding routes are resident in production.
- [x] Portfolio E5 Small and Portfolio GTE Small were genuinely trained, audited,
  transferred, checksum-verified, and mounted read-only.
- [x] Visitors can choose embedder, generation route, top-3/top-5/top-7 retrieval, and
  history-aware follow-up expansion.
- [x] The site exposes fine-tune status, query transform, score threshold, retrieved
  evidence, similarity, requested/served models, fallback state, and stage latency.
- [x] Recruiter/interviewer retrieval and live-answer suites cover experience,
  leadership, projects, concurrency, RAG engineering, privacy, typos, follow-ups,
  unsupported questions, and prompt injection.
- [x] `RAG_GUIDE.md` explains RAG from first principles through this exact training,
  serving, security, evaluation, deployment, and troubleshooting implementation.

## Frozen training evidence

Training uses pinned base revisions, seed `20260712`, 102 reviewed train questions,
62 development questions, and a 16-question v3 locked holdout. Manifests record all
dataset/recipe hashes, software versions, optimizer steps, state checksums, metrics,
and per-file artifact checksums.

| Artifact | Optimizer steps | Dev R@1/R@3/R@5 | Dev MRR | v3 heldout R@1/R@3/R@5 | Heldout MRR |
| --- | ---: | --- | ---: | --- | ---: |
| Portfolio E5 Small | 27 | .629/.919/.968 | .785 | .563/.938/1.000 | .745 |
| Portfolio GTE Small | 52 | .645/.887/.968 | .774 | .563/.813/.938 | .708 |

Both manifests report a changed model state, nonzero optimization, safetensors-only
exports, and passed development gates. The transferred archive SHA-256 was
`7ac0b23373170439bf4c63e5dddc93bd14168e77e138398c71f26d1d34f4d096`.
The VPS independently rechecked every manifest file hash before promotion.

## Production retrieval and answer evidence

The independent 21-question database/qrel suite, run against production vectors at
top five, reported:

- Portfolio GTE: Recall@1 `.667`, Recall@3 `.881`, Recall@5 `.952`, MRR `.803`,
  required-evidence coverage `.952`, mean query time `29.2 ms`; all retrieval gates
  passed.
- Portfolio E5: Recall@1 `.690`, Recall@3 `.857`, Recall@5 `.857`, MRR `.778`,
  required-evidence coverage `.857`, mean query time `30.7 ms`; it is retained as an
  honest comparison route and does not claim to beat GTE.

Live SSE answer runs were repeated across both custom routes with real Groq generation.
The strict locked contract score remained conservative because several correct answers
used wording outside the locked regexes; one locked regex also falsely flags the correct
phrase “does not store raw client IP addresses.” Manual answer review found nine of ten
top-seven GTE heldout answers factual and useful. The real known miss is one booking-
concurrency question that can still retrieve the wrong context and refuse. This is
documented rather than hidden; the site remains above the requested “good enough” bar,
not perfect.

Safety cases for general coding, unsupported salary requests, prompt injection, stale
employment, and raw-IP privacy were exercised. The system prompt now requires literal
`[S#]` citations, prohibits mixing facts across project headings, does not append a
refusal after a supported answer, and prevents broad false privacy claims.

## Exact production-image evidence

Six-model smoke under the production CPU image and limits:

- all expected IDs loaded in order;
- dimensions `384/384/768/1024/384/384` matched configuration;
- custom E5/GTE query encoding took approximately `27/31 ms`;
- full registry RSS was approximately `2,095 MiB` in the smoke process;
- both local artifacts loaded as the unprivileged container user from the read-only
  `/model-artifacts` mount.

The first smoke correctly caught that the exported weight file was owner-readable only.
Deployment permissions were corrected to `a+rX,a-w`: immutable to the container but
readable by UID 10001.

## Current deployment evidence

Deployed feature revision: `249cd75` (`main`, pushed to GitHub and built on the VPS).
This deployment record is committed afterward and does not change the running image.

- Public and loopback `/v1/health` both report `status=ok`.
- Database contains 3 documents / 17 chunks.
- Vector coverage is 17/17 for all six columns.
- API reports the exact same six IDs in `loaded` and `expected`.
- Strict CORS echoes only the Vercel production origin in the verified preflight.
- API and PostgreSQL bind only to `127.0.0.1`; Caddy owns the public IPv4 ports 80/443.
- SSH, fail2ban, Tailscale, host PostgreSQL, and the pre-existing loopback services remain
  active with their audited listeners.
- Current `docker stats`: API `489.6 MiB / 3.418 GiB`, PostgreSQL
  `30.7 MiB / 384 MiB`, Caddy `14.9 MiB / 96 MiB`.
- Local and VPS Git worktrees were clean at the audited source revision.

## Public browser verification

The deployed Vercel UI showed pipeline online, 6 resident embedders, 3 LLM routes, and
7 default chunks. The custom GTE route displayed “portfolio fine-tune,” symmetric text
encoding, threshold `0.77`, and top seven/history-on. Top three/history-off was selected
and observed in the active readout, then defaults were restored.

A real public question—“What measurable engineering impact did Yash have at AIVID
Techvision?”—completed on Portfolio GTE + GPT-OSS 20B with a concise `[S1]`-cited answer,
seven visible source cards, `0.906` top similarity, `41 ms` embedding, `6 ms` retrieval,
`565 ms` first token, and `694 ms` total latency.

## Verification commands

- Backend: 62 tests passed.
- Ruff: all application, tests, scripts, training, and evaluation paths passed.
- Frontend: TypeScript, ESLint, 2 Vitest tests, and Vite production build passed.
- Git diff whitespace validation passed.
- VPS Compose configuration validated with the production engine.
- Public HTTPS health, strict CORS, container health, model smoke, vector coverage,
  artifact checksums, warmed resources, and listener/service parity passed.

## Optional branded DNS

No A records currently resolve for `rag.yashx.me` or `rag-api.yashx.me`. The deployed
fallback URLs are operational. When the owner is ready, add:

- `A rag-api 178.104.56.243`
- the Vercel-provided record for `rag.yashx.me`

Then change the VPS API domain variables and Vercel `VITE_API_URL`, recreate API/proxy,
and repeat public health, CORS, TLS, and browser checks. This optional branding step is
not required for the currently working playground.
