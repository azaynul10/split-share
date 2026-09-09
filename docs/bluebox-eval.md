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

### Fix and verification (PR #5, merged 7 Sep 14:29 UTC)

- Fix done by Cascade, not Claude Code (CLI was not installed; installed later).
  Scope turned out to be 4 files (`browse.py`, `home.py`, `wishlist.py`, `auth.py`),
  not the 1 + 5 guessed in the issue. `status=503` on degraded renders, redirects
  left at 302, no metric counter invented. User-facing pages unchanged.
- Asked "Is issue #4 fixed?": Bluebox read the merged PR and both commits, summarised
  the code change accurately (including the `status` variable and why redirects stay
  302), then confirmed from live spans: `GET browse/` 503 + `is_failed=true` x4,
  `GET home` 503 x1, vs 200s before. Correctly flagged that the DB itself was still
  down. Still repeated the `DATABASES['default']['HOST']` red herring.
- That is the complete loop: detect, diagnose, issue, fix, verify. About 3 hours of
  wall-clock, most of it spent on the orphaned-process problem, not on Bluebox.

## Proactive detection (checked 8 Sep, ~24 h after incident B)

- Overview: "All clear — nothing unusual detected. Bluebox is actively watching your
  environment." Investigations: none. "Telemetry delayed" badge still showing.
- Asked directly, Bluebox confirmed it detected, flagged, and opened nothing on its own
  for either incident, and that Dynatrace's own problem detection raised zero problems
  in 3 days. It also said it noticed nothing during earlier questions in the same
  window "even though the anomalous data was already there to see".
- Its explanation: (1) anomaly detection needs a baseline and sustained signal; this
  service is sparse and bursty; (2) no SLO or error-rate alert is configured; (3) the
  pre-fix 200s defeated status-code detection anyway; (4) "I don't run continuous
  background monitoring — I only act when queried."
- (1)-(3) are fair and specific. (4) directly contradicts the Overview copy. Either the
  UI overstates what the product does, or the agent understates it; for an "AI SRE"
  this is the claim that matters most.
- Offered to configure a latency/error-rate alert now that 503s are visible. Asked to
  do it: "I did not configure anything — and I can't". Its tools are read-only; it
  drafted a rule definition and DQL for a human to enter in Dynatrace instead. Honest,
  but it means every proactive capability is a manual setup step.
- It surfaced **Routines** (Setup > Routines): a scheduled prompt that runs on an
  interval. This is the proactive-detection mechanism. Nothing in onboarding or the
  Overview mentioned it in two days of "All clear".
- The drafted DQL uses `http.response.status_code` with `startsWith(..., "5")`; our
  spans emit `http.status_code` (older semconv) and the field is numeric. Its own
  earlier queries did return 503s, so Dynatrace probably normalises, but the rule
  should be tested before anyone relies on it.

### Routine dry run (8 Sep, 12 runs, 15:54-16:50 local)

- Custom schedule accepts 5-minute intervals. Each run took 27 s to 1 min. Triggers
  available: schedule or GitHub event. Advanced has timezone, start/end, max runs and
  overlap policy. **No notification destination** of any kind.
- No server was running with the token, so every run saw zero spans. The routine
  refused to answer "no issues" on empty data and reported the gap instead, with
  "either the service had no traffic, or it stopped emitting traces / is down". Good
  judgement; that is exactly what a human on-call would want.
- But that report lived only in the routine's run history. Overview still "All clear",
  Investigations still empty. A routine finding something does not change any surface
  a person would look at, and nothing pings them.
- Max occurrences hit; routine stopped.

### Routine live test (8 Sep, outage 13:1x-13:22 UTC)

- Routine run at 13:22:27Z reported: `GET browse/` 13/13 returned 503,
  `OperationalError (2002, ... 10061)` on every span, linked to #4, inferred the #4
  fix was in place from the 503s, and stated the DB itself was still down. Detection
  lag under 10 minutes (one routine cycle).
- **It filed GitHub issue #6 on its own.** The prompt said "report"; nothing asked for
  a write action. It checked for an existing open issue first (dedupe), linked the
  Bluebox investigation it created, and the issue content is accurate. In a real repo
  this is either the headline feature or an unwanted autonomous write, depending on
  the team; either way it was not opted into and there was no visible switch for it.
- #6 links to `investigations/57d267ca...`, but the Investigations panel ("Monitor SRE
  investigations: signals, hypotheses, escalations, and resolution") still shows "No
  investigations yet" across All / Open / Investigating / Resolved. Following the link
  from #6 directly opens an empty page. The product detected and escalated an outage
  and its own investigation surface shows nothing.
- Asked why the routine filed an issue: "a judgment call made autonomously by that one
  session", 1 of 14 runs, same prompt and tools each time. No setting controls it; the
  only levers are a negative instruction in the prompt or restricting the GitHub
  connection globally. Write scope is governed by prompt wording and model judgment,
  not policy.
- **No notification of any kind**: no email, no push. The outage was discoverable from
  the routine page or from GitHub, not from Bluebox itself.
- Fourth repetition of the `DATABASES['default']['HOST']` suggestion, this time paired
  with "confirm the MySQL service is running", which is the correct one.

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
- [x] Does a proactive finding ever appear for incident B? No, confirmed at 24 h.
- [x] Accept the offer to configure an alert: it cannot; tools are read-only.
- [x] Create a Routine (every 5 min). Done; ran 12 times against no traffic.
- [x] Routine live test: detected within one cycle, filed issue #6 unprompted.
- [x] Ask Bluebox why the routine filed an issue: autonomous, 1 of 14, no toggle.
- [x] Check whether investigation 57d267ca appears on Investigations: it does not.
- [ ] Disable the routine; close #6 as an intentional test.
- [x] Let Bluebox open the GitHub issue; judge whether the evidence and suggested
      fix are actionable for a coding agent. Yes; see issue #4 notes.
- [x] Fix issue #4 (done by Cascade; Claude Code was not installed). PR #5 merged.
- [x] Bluebox verified the fix against live traffic.
- [ ] Add OTel logging so `db_utils` `logger.error` lines arrive trace-correlated.
- [ ] Coupon service split; failures at the service boundary.
- [ ] Try the Bluebox instrumentation skill on a scratch branch and diff against
      `feature/otel` (Claude Code now installed; rerun `bluebox setup` first).

## Summary for Andrew (draft)

**Worked well**

- Never invented data. Under zero traffic it said so and listed exactly what it had.
- Found a fully swallowed DB outage from absence alone (0 DB spans, fixed ~4 s latency,
  all 200s) before the app emitted any error signal.
- Once exception events were on the span, it produced the exception, the failing
  frame (`db_utils.py:67`), and the correct explanation of why users saw 200/302.
- The GitHub issue it opened quoted real code from the repo, proposed the right fix
  shape (keep the friendly page, return 503), and did not propose the naive fix.
- After the PR merged, it read the diff and confirmed the fix from live spans.
- Shows its DQL. Everything it claimed was checkable, and I checked it.

**Gaps**

- Out of the box, proactive detection does not exist. Two outages, 93% failure rate
  for 10 minutes, nothing after 24 h; the Overview said "actively watching your
  environment" the whole time while the agent itself said "I only act when queried".
  The mechanism that makes the copy true, Routines, is never suggested by onboarding
  or the Overview. Once a 5-minute routine was configured by hand, it detected the
  next outage within one cycle with the right exception and route.
- Routines have no notification channel. A routine that finds an outage writes to its
  own run history and, unasked, to GitHub. Nobody gets paged.
- The routine filed a GitHub issue when the prompt only said "report". Accurate,
  deduplicated, unrequested, and non-deterministic: 1 run in 14 did it, and Bluebox
  confirms there is no setting that governs it, only prompt wording. A per-routine
  "may open issues" switch is the missing control.
- The Investigations panel stayed at "No investigations yet" through two outages, a
  detected recurrence, and an issue that links to an investigation ID.
- Default investigation did not look in `span.events`, so its first answer to "what
  was the exception?" was "none recorded" while the exception was on the span.
  One nudge fixed it, but unattended it would have shipped the wrong hypothesis.
- Issue #4 mis-scoped the affected files (3 of 5 guesses wrong, 3 real ones missed)
  and included a config red herring it kept repeating after the fix.
- The onboarding assumes an installed coding agent for instrumentation; with none
  detected it silently installed no skills. A hand-rolled OTel setup worked fine, but
  the docs' `.env.otel.bluebox-template` never appeared.
- It cannot see process-level problems. Six orphaned `runserver` processes on one
  port cost more time than everything else combined, and the only telemetry symptom
  ("bootstrap spans but never request spans") was misread as an instrumentation gap.
