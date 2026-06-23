# Local demo and silent one-minute video guide

This guide presents one safe, synthetic portfolio demo of a regulated case workflow. It uses only
`demo.invalid` accounts and invented content. Do not use real personal data, passwords, or
screenshots containing secrets.

## Set up before recording

Run this from the repository root. The command enables local deterministic providers for indexing
and direct RAG answers; it makes no external model calls and does not claim model or search quality.

```bash
NORDIC_API_EMBEDDING_PROVIDER=deterministic \
NORDIC_API_RAG_COMPLETION_PROVIDER=deterministic \
pnpm dev:up

docker compose --env-file .env.example exec api \
  alembic -c apps/api/alembic.ini upgrade head

read -r -s NORDIC_LOCAL_SEED_PASSWORD
export NORDIC_LOCAL_SEED_PASSWORD
docker compose --env-file .env.example exec -T \
  -e NORDIC_LOCAL_SEED_PASSWORD api \
  python scripts/seed_phase34_demo.py \
  --password-env NORDIC_LOCAL_SEED_PASSWORD
```

The seed command prints one JSON line containing safe UUIDs, `demo.invalid` email addresses, and
technical routes. The technical routes are support information only: **do not** paste them or show
them in the recording. Each call adds a separate synthetic demo case and does not remove prior data.

### Prepare one API paste before recording

Before you start recording, copy **only the value** beneath `rag_answer_request` from the new seed
output to your clipboard. It is the only text to paste while recording. Copy the complete inner JSON
object, including its outer braces, but not the entire seed line or the `rag_answer_request` name.

The object always has this form. Use the actual `case_id` from the seed output, not the placeholder:

```json
{
  "answer_language": "en",
  "case_id": "<case_id-from-the-new-seed-output>",
  "question": "What must be documented before an answer can be used?"
}
```

Prepare this before screen recording. Once recording begins, use only the browser and the
application navigation. Do not include the terminal, seed output, or UUID routes in the recording.

Use an invented local password phrase. Do not show it, put it in a script, store it in history, or
include it in the video. After recording:

```bash
unset NORDIC_LOCAL_SEED_PASSWORD
pnpm dev:down
```

## Recording sequence — about 60 seconds

The recording must be completely silent. Show only the following actions in the stated order and
time ranges.

1. **0–7 s:** Open `http://127.0.0.1:3000/en/login`, sign in as
   `kari.eksempel+caseworker@demo.invalid`, and open the newest case titled
   _Synthetic accommodation request_.
2. **7–17 s:** Show _Waiting for human review_ and _High risk_. Open **Documents**, select
   _Synthetic case-handling procedure_, and choose **Inspect metadata**. Show parsing, indexing,
   and approved source status.
3. **17–28 s:** Scroll to **Structured information** and choose **Open workflow trace**. Show the
   status, timeline, and safe final state.
4. **28–38 s:** Open `http://127.0.0.1:8000/docs` in a new tab. Open
   `POST /api/retrieval/answer`, choose **Try it out**, replace the example body with the prepared
   JSON object, and choose **Execute**. Show `answered`, `[S1]`, and the source object in the result.
5. **38–50 s:** Return to the application tab, sign out, and sign in as
   `ole.eksempel+reviewer@demo.invalid`. Open **Approvals**, select the review packet for the same
   `DEMO-34-…` case, choose **Edit and approve**, enter a short synthetic final text, and confirm.
6. **50–60 s:** Sign out, sign in as `per.eksempel+admin@demo.invalid`, open **Audit**, and show the
   new events. Then open **Evaluations** and the newest run using **Open run**.
