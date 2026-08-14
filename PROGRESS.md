# RAG Playground deployment record

Last updated: 2026-08-14 13:11 IST

## Goal status

The public portfolio RAG is deployed at `https://www.yash456k.com`. Its API is served
through the valid-TLS hostname `https://178-104-56-243.sslip.io`.

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

Deployed feature revision: `ef69510` (`main`, pushed to GitHub and built on the VPS).
This deployment record is committed afterward and does not change the running image.

- Public and loopback `/v1/health` both report `status=ok`.
- Database contains 3 documents / 22 chunks.
- Vector coverage is 22/22 for all six columns.
- API reports the exact same six IDs in `loaded` and `expected`.
- Strict CORS accepts `https://www.yash456k.com`; the retired `https://rag.yashx.me`
  origin is rejected with HTTP 400 and is absent from the production environment.
- API and PostgreSQL bind only to `127.0.0.1`; Caddy owns the public IPv4 ports 80/443.
- Current `docker stats`: API `501.9 MiB / 3.418 GiB`, PostgreSQL
  `34.01 MiB / 384 MiB`, Caddy `22.48 MiB / 96 MiB`.
- The deployed API image contains the `www.yash456k.com` OpenRouter referer and no
  `rag.yashx.me` referer.

## Public browser verification

The custom domain serves the current Vercel build with canonical and OpenGraph URLs set
to `https://www.yash456k.com/`. The public config reports six resident embedders, five
LLM routes, top-three retrieval by default, and history-aware retrieval enabled.

A real public question—“What is Yash's portfolio URL?”—completed on Portfolio GTE +
GPT-OSS 20B with the cited answer `https://www.yash456k.com` from three source chunks.
The top similarity was `0.88661`; embedding took `26.6 ms`, retrieval `4.9 ms`, first
token `415.0 ms`, and the full streamed answer `438.4 ms`. Twenty token events and one
clean `done` event arrived with no fallback or error.

## Verification commands

- Backend: 74 tests passed under the production Python 3.12 image.
- Ruff: all application, tests, scripts, training, and evaluation paths passed.
- Frontend: TypeScript, ESLint, 4 Vitest tests, and Vite production build passed.
- `npm audit` reported zero vulnerabilities after the lockfile refresh.
- Git diff whitespace validation passed.
- VPS Compose configuration validated with the production engine.
- GitHub backend/frontend CI and the Vercel deployment passed for `ef69510`.
- Public HTTPS health, strict CORS, container health, re-ingestion, vector coverage,
  custom-domain metadata, and a real public SSE answer passed.

## Branded DNS follow-up (retired)

The branded DNS plan considered in this record was never activated and is no longer a
current deployment step. The current public portfolio is `https://www.yash456k.com`,
while the live API remains `https://178-104-56-243.sslip.io`.

Any future branded API hostname would require coordinated DNS, VPS API domain, proxy,
and Vercel `VITE_API_URL` changes followed by public health, CORS, TLS, and browser
verification.
