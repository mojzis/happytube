# Phase 4 — log

Loop (planned): dev → review ‖ QA (QA runtime-only, incl. a browser look) → fix →
combined verify → learnings.

Decisions taken with the user before dev (2026-10-28): reviewer = name field
remembered in a cookie (default from config); channels only (video queue → phase
5); local only (127.0.0.1, no auth); package `review/` + `happytube serve`.

## 1 — dev
Report (verbatim JSON, abridged formatting):

- commits: d8b4bd1 docs; 387d9be deps (fastapi 0.162, uvicorn 0.54, python-multipart
  0.0.32, starlette 1.10; httpx dev); 4455e17 htmx 2.0.11 vendored (unpkg, sha256
  matches npm tarball); f8d4e87 review app; cf1d929 `happytube serve`; 8170100
  decision 0007, CLAUDE.md, architecture.
- tests: 369 passed (was 298), coverage 78% (was 75%; review/queue.py 100%,
  cli/serve.py 100%, review/app.py 98% — one unreachable ValidationError fallback).
- real_run (curl, scratch copy, no keys): queue + htmx filter partial OK; detail for
  zoo-praha / smithsonian (inactive) / ct-decko (unresolved) OK; 404 unknown slug;
  htmx POST approve → OOB badge `approved`, notes escaped, cookie URL-encoded,
  HttpOnly, SameSite=strict, 1 y; plain POST → 303; empty reviewer 422 nothing
  written; forged Origin / Sec-Fetch-Site cross-site → 403; bad Host → 400; broken
  channel.yaml → 500 naming file, no traceback; files only in the copy.
- eyeball: queue order as specified; names sort without diacritic awareness (ČT with
  C). Not checked in a real browser.
- deviations: `create_app(bind_host=…)`; `_status_badge.html` for OOB, htmx target
  is whole #reviews section; htmx `responseHandling` config to swap 422;
  history-restore gets full page, `Vary: HX-Request`; cookie URL-encoded; unknown
  filter value → 400; deptry ignores python-multipart (DEP002) + starlette (DEP003),
  404 handler on Starlette HTTPException, vulture ignores for FastAPI/click
  decorators + QueueSections fields; `channels_dir_option` shared in cli/channels.py.
- unresolved: `--host 0.0.0.0` accepts only loopback Host + literal 0.0.0.0 (LAN IP
  → 400); one broken file → whole queue 500 (as specified); no browser check.

## 2a — review
Verdict `ship`. Findings (verbatim, abridged):

- R1 medium — htmx POST getting 400/403/404/500 shows nothing (responseHandling swaps
  only 422); reproduced with broken channel.yaml → silent 500. Fix: swap error page
  into `<main>` or `htmx:responseError` listener into a role=alert region; test.
- R2 low — wildcard `--host` (0.0.0.0/::) warns, then 400s every real client; a
  non-loopback IPv6 bind_host is never allowed (`host_name('fe80::1')` → None). Fix:
  refuse wildcard binds with a hint; bracket bare IPv6 / use `ipaddress`; test; 0007.
- R3 low — async routes do sync file I/O. Fix: plain `def`.
- R4 low — parse_review/parse_filters return str-or-value unions; parse_filters(**)
  untyped, KeyError on unexpected key. Fix: raise FormError; explicit params.
- R5 low — every CLI command imports fastapi/uvicorn (~200 ms). Fix: import in serve().
- R6 low — test naming/split/missing asserts (test_review_app.py:274,306;
  test_cli_serve.py:271 ipv6 url).
- R7 low — hand-rolled status constants (use HTTPStatus); review counts in Jinja.
- Deviations: all accepted; diacritic sort accepted (not worth ICU for ~15 rows);
  whole-queue 500 on broken file accepted (as specified).

## 2b — QA
Verdict `ship`. poe check green (369, 78%). Browser (Chrome, scratch copy): queue
order per spec; htmx filter swaps + URL + back; detail pages incl. thumbnails,
resolved-to, unresolved ct-decko; htmx approve updates reviews + badge, notes
escaped; 422 shown in form, values kept; cookie prefill (HttpOnly) and
HAPPYTUBE_REVIEWER prefill; no console errors; only i.ytimg.com external. Wheel
contains templates/static, serves from /tmp. Concurrent CLI+web writes: 9/9 files,
-2/-3 suffixes, nothing overwritten, latest verdict right. Old commands OK.
Screenshots in session scratchpad `p4-qa-shots/` (not committed).

- Q1 low — port in use: banner printed, then raw uvicorn `[Errno 98]`, exit 3.
- Q2 low — `--host 0.0.0.0`: LAN IP Host → 400 (= R2).
- Q3 low — installed wheel: default `--channels-dir` → `<venv>/lib/python3.12/channels`,
  silently empty (preexisting PROJECT_ROOT default, shared with `channels`).
- Q4 low — the two queue tables' columns don't line up.

## 3 — fix
Commits 0c27040..e02df23 (7). 398 passed, coverage 78%.

- R1: htmx errors returned as text/plain with real status; `static/review.js`
  (~15 lines) on `htmx:responseError`/`sendError` writes textContent into a
  role=alert `<p class=htmx-error>` in the form (fallback `<main>`). Plain requests
  still get error.html.
- R2 (Q2): `serve` refuses 0.0.0.0 / :: / [::] (BadParameter, exit 2); Host check via
  `ipaddress` canonical forms; LAN IPv4/IPv6 bind works; 0007 updated.
- R3 plain `def` routes; R4 `FormError`; R5 lazy imports + subprocess test; R6 tests
  split/asserts; R7 HTTPStatus + `ChannelEntry.human_/agent_review_count`.
- Q1: socket probe before banner → one-line error, exit 1. Q4: `table-layout: fixed`.
- deviations: probe race window; all htmx errors plain text (422 still swaps form);
  `[]` stripped from --host; serve tests stub the probe; CSS commit precedes JS.
- unresolved: htmx alert JS not tried in a real browser.

## 4 — verify (combined)
Verdict `ship`. R1, R2, R3–R7, Q1, Q4 resolved (browser: htmx 400/500 alerts shown
as plain text in the form's role=alert box, hidden again on next request; approve
still works; columns line up). Q2 partial → V1. All 4 fix deviations accepted.
Safety: every tricky Host rejected (userinfo, trailing dot, 0x7f.1, 127.1, octal,
decimal, [::ffff:127.0.0.1], [::1%lo], bad ports); Origin exact; textContent only.
Screenshots in session scratchpad `p4-verify-shots/` (not committed).

- V1 low — `serve --host 0` not caught as wildcard (`ipaddress` rejects '0',
  getaddrinfo binds 0.0.0.0). → backlog.
- V2 cosmetic — multi-line store errors collapse in the alert. → orchestrator fix:
  `.htmx-error { white-space: pre-wrap; }` (CSS only, logged here).
