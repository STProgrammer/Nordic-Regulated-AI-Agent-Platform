# Deterministic AI Evaluation

Phase 25 provides a synthetic-only regression signal. It is deliberately not a hosted-model judge,
semantic-faithfulness score, language-quality score, latency report, or release gate.

## Corpus and local check

The checked-in canonical corpus is
[`sample-data/evaluation/nordic-regulated-core-v1.json`](../sample-data/evaluation/nordic-regulated-core-v1.json).
It is versioned, Pydantic-validated, content-hashed, and contains only invented logical source keys
and short Norwegian Bokmal/English questions. Do not add personal data, identifiers, URLs, storage
paths, credentials, copied customer material, database UUIDs, or provider settings.

Run its provider-free regression check from the repository root:

```bash
uv run python scripts/run_evals.py --dataset nordic-regulated-core-v1 --check
```

The command needs neither PostgreSQL nor a model, embedding provider, network connection, or
credentials. It prints only dataset identity, content hash, totals, fixed metric pass counts, and
overall pass/fail; it exits non-zero if any required exact behavior differs.

The deterministic measurements are:

- Retrieval source-key precision and recall.
- Citation-key precision and recall.
- Structural answer-criterion support, not semantic entailment or prose quality.
- Expected refusal behavior.
- Closed final-risk outcome.
- Closed Intake routing outcome.

Every canonical case is an exact regression: an unexpected logical key, a missing expected key, or
any closed outcome mismatch fails that case and the run.

## Persisted operations

Authenticated Administrators can inspect canonical datasets, start one current-organization run,
list their organization’s runs, and inspect safe per-case metric outcomes:

- `GET /api/evaluations/datasets`
- `POST /api/evaluations/datasets/nordic-regulated-core-v1/runs` with `{}`
- `GET /api/evaluations/runs`
- `GET /api/evaluations/runs/{evaluation_run_id}`

The start request has an intentionally empty strict JSON body. The API never accepts an
organization, corpus, fixture, source, provider, threshold override, prompt, or arbitrary result
payload from a caller. The Celery message carries only the evaluation-run UUID; the worker reloads
the canonical dataset and stores a compact status, aggregate summary, numeric scores, pass/fail, and
closed failure codes. Questions, prompts, raw evidence, model outputs, provider exceptions, and
workflow snapshots are excluded from responses, audit metadata, and run/result records.

For local stack inspection, run migrations explicitly, authenticate with the existing synthetic
Admin fixture, then use the API documentation at `http://127.0.0.1:8000/docs`. The dedicated
`evaluation` Celery queue is consumed by the standard local worker. There is no Phase 25 dashboard;
charts, trends, exports, hosted judging, cost/latency analysis, and CI release gating are later
work.
