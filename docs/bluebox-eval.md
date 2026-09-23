# Bluebox evaluation notes

Working notes from instrumenting Split Share with OpenTelemetry and pointing it at
Bluebox (Dynatrace tenant `njh16107`). Chronological.

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

## Phase 2: coupon service split (9 Sep)

- `coupon_service/` (Flask, :8001) owns promo-code pre-checks; Django calls it over HTTP
  with a 2 s timeout. Refused -> 503, timeout -> 504, upstream 5xx -> 502, all recorded
  on the span. Trace context propagates via the requests instrumentor. Fault switch at
  `/_fault?mode=slow|error|none`. Branch `feature/coupon-service`.
- First question, on a single 502 event: Bluebox followed the trace across the boundary,
  named `peer.service: split-share-coupons`, the downstream `POST /validate` 500, the
  `CouponServiceError`, and the honest 502. Said explicitly the fault is downstream, not
  the web app or the database. Correct on every point.
- It found a real bug from telemetry: both services reported `dt.service.name:
  split-share-web`. Cause was `OTEL_SERVICE_NAME` in the shared `.env.otel` template
  overriding the coupon service's default. Its guess ("missing OTEL_SERVICE_NAME on the
  dependency") had the mechanism inverted but the location right. Fixed in 1f4ae51.
- Declined to file an issue: one event, and no branch it checked contained the code. It
  searched `main` and `feature/otel` only; the code was on `feature/coupon-service`.
  Reasonable restraint, and a different call from the routine that filed #6.
- Asked "which service is at fault, the promo box has been failing today" before any
  failures had been generated. Bluebox rejected the premise: two requests in 3 days, one
  502 yesterday, one 200 a minute ago, "I'd hold off on treating this as an active
  incident". Checked logs for coupon mentions too. Correct refusal to invent a pattern.
- **Stale repo view.** At 10 and again at 20 minutes after PR #7 merged, Bluebox said
  `main` contains no `CouponServiceError` and no outbound call. Raw GitHub for `main`
  showed both at the same time. For a product whose output is "a GitHub issue that cites
  the code", reading a stale `main` is a correctness problem, not a cosmetic one.
- Second question, after 2 `error`-mode attempts: correct table of the 3 requests, correct
  single failure mode, correct attribution to `split-share-coupons`, did not invent the
  modes that had not been run. Called it "intermittent", a fair read of 200/500/500.
  Offered to file an issue and asked first; in chat it asks, in a routine it does not.
- Coupon service still reported as `split-share-web`; the `OTEL_SERVICE_NAME` line was
  still in the local `.env.otel` for that run.

### Three-mode test (23 Sep)

**slow** (06:41-06:42 UTC, 1 baseline + 3 attempts):

- Bluebox produced the exact table: 200 in 17 ms, then 504 x3 at 2.02-2.14 s. Named the
  mechanism precisely: web gives up at the 2.0 s read timeout (`coupons.py:68`,
  `requests.exceptions.ReadTimeout`), while the downstream `POST /validate` span shows
  the coupon service **did answer 200, ~5 s later**. Called it a latency mismatch, not a
  downstream error, and distinguished it from the 500s on 9-10 Sep. All correct; the
  5 s figure is the injected `time.sleep(5)`.
- Attribution: coupon service at fault (~300x slowdown from baseline); web "handled the
  timeout correctly, returning a real 504 rather than swallowing it". Also volunteered
  that 2 s is arguably too tight for that dependency's tail. Fair engineering read.
- Recognised this as a third occurrence with two distinct signatures and proposed a
  pattern-level tracking issue instead of another one-off. Asked before acting.
- Claimed the coupon spans still carry `dt.service.name: split-share-web`. `/health` on
  the running process said `split-share-coupons` at the same moment, so the claim was
  either about older spans or wrong; see below.
- **Still cannot find `coupons.py` or the coupon service in the connected repo**, 13 days
  after PR #7 merged to `main`. The stale-repo problem is not a cache delay; something
  about how it indexes the repo is not picking up post-connection files.

**down + slow (again) + error** (06:53-06:55 UTC), asked as one question: "list every
failure grouped by signature, name the service at fault for each, and what `service.name`
do the coupon service's own spans carry now":

- 23 requests, four clusters, one table, every row correct:
  `ReadTimeout` 504 x3 (downstream answered 200 ~5 s later), `ConnectTimeout` 503 x3
  (**no downstream span exists**, process not accepting connections), `ReadTimeout` 504
  x3 again, `CouponServiceError` 502 x6 caused by downstream 500 with the message
  "Injected fault: coupon rules engine unavailable" raised at `coupon_service/app.py:105`.
  Then six 200s at 7-23 ms: "the dependency recovered". Counts, statuses, windows and
  line number all match the servers' logs and the source.
- Attribution: coupon service at fault in all four; web "returned an honest, distinct
  error status (503/504/502 matching the specific cause)". Explicitly contrasted with the
  Sep 6-8 DB incidents where failures hid behind 200s. That is the intended design and
  it read it off the telemetry unprompted.
- Read "Injected fault" in the exception message and inferred "a deliberately injected
  test fault ... an active reliability/chaos exercise rather than a single incident".
  Correct, and the right level of scepticism before filing anything.
- Confirmed `dt.service.name: split-share-coupons` on the downstream `POST /validate`
  spans, distinct from `split-share-web`. So the identity fix is live and its earlier
  "inherits split-share-web" was stale. Also noted the residual gap: when the service is
  fully down there is no downstream span at all, so "down" is only visible as a
  client-side symptom on web, not as an availability signal on the coupon service.
- `app.py:105` came from the stack trace in the span event, not the repo; it still said
  it cannot find the coupon code in the repository. Trace-derived facts were correct;
  repo-derived facts remain 13 days stale.
- Asked before filing/updating a tracking issue (chat behaviour consistent: asks).

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
- [x] Coupon service split; failures at the service boundary. PR #7 merged.
- [x] Full three-mode coupon test (slow / error / down) with the service-name fix live.
      All four signatures attributed correctly; service identity confirmed fixed.
- [ ] Try the Bluebox instrumentation skill on a scratch branch and diff against
      `feature/otel` (Claude Code now installed; rerun `bluebox setup` first).
