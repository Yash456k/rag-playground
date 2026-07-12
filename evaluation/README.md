# Portfolio RAG evaluation

This directory defines deterministic retrieval qrels and answer contracts for questions a
recruiter, interviewer, or hiring manager might ask. `dev.json` is available for training-data
review, failure analysis, and threshold calibration. `heldout.json` is a locked final test split:
never add its questions or paraphrases to training data, hard negatives, prompt examples, or
threshold tuning.

Each factual case contains source-and-chunk evidence groups. A qrel option combines a source,
the current deterministic chunk indexes, and a section-specific content regex. The regex prevents
an overlapping but wrong section from counting and makes intentional re-chunking easy to review.
Answer contracts use regex alternatives instead of exact prose, require cited retrieved evidence,
and reject stale or fabricated claims. Refusal cases test unsupported requests and prompt
injection. The suite also contains misspellings and conversation-history follow-ups.

`heldout.sha256` is verified automatically whenever the held-out split is loaded. Changing the
held-out file without an intentional lock update fails closed. If a corpus edit changes chunk
indexes, review qrels against `app.ingest.chunk_document`; do not relax claims based on model
outputs.

Run retrieval evaluation inside an environment that has the configured model artifacts and the
ingested PostgreSQL database:

```bash
python -m scripts.evaluate_retrieval --split all
```

The command emits a JSON summary and JSONL case records. Gates apply independently to every
embedder: Recall@1/3/5, MRR@5, and complete required-evidence coverage at rank five.

Run live answer evaluation against a reachable API. The default selection comes from `/v1/config`;
repeat `--embedder` or `--model` to compare routes. `--case`, `--category`, `--split`, and `--runs`
support focused and repeated checks. A request budget prevents accidentally exhausting the public
daily rate limit.

```bash
python -m scripts.evaluate_answers \
  --base-url https://api.example.test \
  --split dev --runs 2
```

For operator-only repeated runs, set `RAG_EVALUATION_TOKEN` in the evaluator process to the
server verification value. The evaluator sends it only in `X-Verify-Evaluation`, never serializes
the header or value, and the browser CORS policy does not permit this header.

Answer JSONL records include the full answer, retrieved chunks and scores, event counts, usage,
requested/served model, fallback attempts, and all stage latencies. They never persist request
headers, environment variables, database URLs, provider keys, or URL credentials. Quality gates
cover completion, expected grounded claims, refusals, forbidden claims, and valid citations that
actually point to required evidence.

Generated reports live under `evaluation/results/` and are ignored by Git.
