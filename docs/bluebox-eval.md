# Bluebox evaluation notes

Working notes from instrumenting Split Share with OpenTelemetry and pointing it at
Bluebox (Dynatrace tenant `njh16107`). Chronological; the summary at the end is what
goes to Andrew.

## Setup

- Instrumentation hand-written (`split_share_core/telemetry.py`), not via the Bluebox
  coding-agent skill. Django + MySQLdb instrumentors, OTLP/HTTP exporter, config from
  standard `OTEL_*` env vars. Console fallback when no endpoint is set.
- Bluebox CLI setup: refused to run in a 13-row IDE terminal (needs 80x20); ran in a
  standalone window. Fresh window did not have the CLI on PATH until reopened.
- Ingest token is shown only in the browser (deliberately kept out of files/CLI).
  Token type `dt0s16` uses `Authorization: Bearer <token>`.
- `.env.otel.bluebox-template` mentioned in the docs was not written for this repo.

## Incident A: DB outage, auto-instrumentation only (6 Sep, 16:38-16:57 UTC)

MySQL stopped; views catch `QueryError` and render a friendly page with HTTP 200.
The MySQLdb instrumentor wraps `cursor.execute`, not `connect()`, so a connection
failure produced **no DB span and no exception** — just a clean-looking SERVER span.

Bluebox, when asked "did anything abnormal happen":

- Found it. Latency pinned at ~4.09 s (Windows TCP connect-refused wait) vs 30 ms
  baseline; **0 DB spans per request** on the slow ones vs 5-6 on the fast ones.
- Correctly noted all requests returned 200.
- Could not name the cause; hypothesised pool wait / upstream timeout / thread
  starvation. Fair — the telemetry did not contain the fact.
- No finding was opened proactively ("hasn't tripped anomaly detection, traffic low").

## Fix: mark swallowed failures on the span

`marketplace/db_utils.py` now calls `span.record_exception()` and sets status `ERROR`
before raising `QueryError`. User-facing behaviour unchanged.

## Incident B: same outage, with the fix (7 Sep, 08:23-08:33 UTC)

- 25/27 requests flagged `request.is_failed`; Bluebox reports "200/302 to users,
  failed internally" and "recurring, worsening pattern" — accurate.
- First answer: **"no exception recorded anywhere"**, having checked top-level
  `exception.type`, `exception.message`, `status.message`. Fell back to the same
  "~4 s timeout/watchdog" hypothesis as incident A.
- When told to look in `span.events`: found `django.db.utils.OperationalError`,
  `(2002, "Can't connect to server on 'localhost' (10061)")`, the stack frame
  `db_utils.py:67 in fetch_one`, and correctly inferred that the calling views catch
  it and render a normal page. Offered to open a GitHub issue.
- Net: the evidence was ingested and queryable; the default investigation path did
  not inspect span events, which is where the OTel spec puts exceptions. One prompt
  fixed it, but an unattended investigation would have shipped the wrong hypothesis.
- Still no proactive finding on the Overview page at time of writing.

### GitHub issue #4 (opened by Bluebox on request)

- Cites `marketplace/views/browse.py` with faithful quotes of the two `except QueryError`
  blocks and `db_utils.py:67`; it read the repo, not just the trace.
- Root cause stated on both layers: DB refused, and views render 200/302 regardless.
- Suggested fix is the right shape: keep the friendly page, return `status=503`, add a
  metric on the except branch. Not the naive "stop catching the exception".
- Inaccuracies: calls the 4.09 s a "hard timeout ceiling" (it is the OS connect-refused
  backoff); lists `seller.py`, `groups.py`, `reviews.py` as likely having the same
  pattern (they do not) while missing `auth.py`, `coupons.py`, `home.py` (they do).
  Hedged with "likely", so not a hallucination, but a coding agent acting on it
  would waste a pass.
- Actionable enough to hand to a coding agent as-is.

## Things that bit us that Bluebox could not see

- Six orphaned `runserver` processes sharing `:8000`. Django sets `SO_REUSEADDR`;
  on Windows that allows multiple live binds with no error. Browser traffic went to a
  stale process without the token. Symptom in telemetry: only startup spans, never
  request spans. Bluebox's read ("HTTP layer not instrumented, or different service
  identity") was reasonable but wrong; the pattern "service emits only bootstrap
  spans, repeatedly" is a candidate heuristic.
- Python OTLP/HTTP exporter (1.38) treats any 2xx as success and never parses
  `partialSuccess`. Not the cause here, but `tools/otel_selftest.py` exists to check it.
- `OTEL_EXPORTER_OTLP_HEADERS` is URL-decoded only when the value is otherwise valid;
  a placeholder with `<>` was sent raw and produced a confusing 401.

## Positives so far

- Honest under no-data: enumerated exactly the 3 spans present, no invented traffic.
- Absence-based reasoning (0 DB spans + fixed latency) found a fully swallowed outage.
- Every answer shows the DQL it ran; easy to verify and to learn the schema from.
- Clear about lookback limits (3 days) and about low-traffic caveats.

## Open items

- [x] Follow-up: does Bluebox see `span.events` on the failed spans? Yes, when asked.
- [ ] Does a proactive finding ever appear for incident B?
- [x] Let Bluebox open the GitHub issue; judge whether the evidence and suggested
      fix are actionable for a coding agent. Yes; see issue #4 notes.
- [ ] Hand issue #4 to Claude Code on a branch; review the PR it produces.
- [ ] Add OTel logging so `db_utils` `logger.error` lines arrive trace-correlated.
- [ ] Coupon service split; failures at the service boundary.
- [ ] Try the Bluebox instrumentation skill on a scratch branch and diff against
      `feature/otel`.
