# Phase 4 — learnings (local review UI)

Branch `phase-4-review-ui`, `06185d1..c42dbdd`, 14 commits, 2026-10-28.
Loop run: dev → review ‖ QA (QA runtime + real browser, separate worktrees) → fix →
combined verify (`ship`) → orchestrator CSS fix (V2) → learnings. This matched
"Loop (planned)" in log.md. No external API, so no credentials and no committed data
run.

## Delivered

- Deps as one commit: fastapi 0.162, uvicorn 0.54, python-multipart 0.0.32
  (starlette 1.10 comes with them); httpx in the dev group for `TestClient`.
- htmx 2.0.11 vendored as `review/static/htmx.min.js` (unpkg, sha256 matches the npm
  tarball; version, URL and hash in the header comment and in 0007).
- `happytube/review/`: `create_app(store, *, default_reviewer, bind_host=None)`,
  pure `queue.py` (sections + sort), templates, `review.css`, `review.js`.
- Queue (needs human review first, attention → vet verdict → name; then reviewed),
  htmx filters with `hx-push-url`, detail page (channel, evidence, vet from the
  frontmatter, reviews), review form writing through `ChannelStore.add_review` only.
- `happytube serve [--host] [--port] [--channels-dir] [--reviewer]`, top level,
  sharing `channels_dir_option` with the `channels` group.
- `ChannelEntry.human_review_count` / `agent_review_count`, used by `summary_dict`
  and the queue.
- Decision 0007, CLAUDE.md, architecture.md.
- Tests 298 → 369 (dev) → 398 (fix); coverage 75% → 78%; `poe check` green.

## What each step found

- **Dev (1)**: built everything; curl real run on a scratch copy covered every
  route, the safety checks and a broken file. Deviations listed honestly
  (`responseHandling` config, `Vary`, deptry/vulture ignores). Flagged its own gaps:
  wildcard `--host` 400s LAN clients, no browser check.
- **Review (2a)**: R1 (medium) — an htmx POST that gets 400/403/404/500 shows nothing
  (htmx 2 swaps no 4xx/5xx by default; the config only added 422). Reproduced with a
  broken channel.yaml. R2 wildcard bind and IPv6 `bind_host`. R3–R7 low (async
  routes doing sync I/O, str-or-value unions, eager fastapi import in every CLI
  command, tests, hand-rolled status codes).
- **QA (2b)**: real Chrome check of everything htmx does; wheel built, installed in
  a throwaway venv and served from `/tmp`; concurrent CLI + web writes (9/9 files,
  nothing overwritten). Q1 port in use → raw uvicorn errno, Q2 = R2, Q3 installed
  default `--channels-dir` points into the venv, Q4 queue columns don't line up.
- **Fix (3)**: R1–R7, Q1, Q4 in 7 commits. Deviations: probe race window, all htmx
  errors as plain text, `[]` stripped from `--host`, serve tests stub the probe.
- **Verify (4)**: all resolved, Q2 partial. Re-checked the Host rewrite against
  tricky inputs and looked at the htmx alert in the browser. V1 `--host 0`, V2
  multi-line alert collapses.
- **Orchestrator**: V2 as one CSS line (`white-space: pre-wrap`), logged.

## FastAPI + htmx facts

- **htmx 2 swaps nothing on 4xx/5xx by default.** A 422 form error needs a
  `responseHandling` entry (here in `<meta name="htmx-config">`). Every other error
  stays silent unless you handle `htmx:responseError` / `htmx:sendError`. Without
  that, a failed write looks like a click that did nothing.
- Error text for htmx requests is plain text with the real status. ~15 lines of JS
  put it into a `role="alert"` box with `textContent` (never HTML) and hide it on
  the next request. Plain requests still get the error page.
- **OOB swap** for the status badge: return the reviews section plus a separate
  `_status_badge.html` with `hx-swap-oob`. Target the whole `#reviews` section, not
  the list, so the form comes back cleared but keeps the reviewer.
- **Same URL, two bodies (partial vs page) needs `Vary: HX-Request`.** Otherwise
  the browser cache or htmx history restore can show a bare partial. History
  restore requests get the full page.
- Unknown routes raise Starlette's `HTTPException`, not FastAPI's. The 404 page
  handler must be registered on the Starlette class.
- Routes that do sync file I/O should be plain `def` (FastAPI runs them in a
  threadpool); `async def` blocks the event loop.
- Import fastapi/uvicorn inside `serve()`. A top-level import costs every CLI
  command ~200 ms. A subprocess test guards it.
- The reviewer cookie value is URL-encoded, so non-ASCII names survive.

## Local-app safety

- A local unauthenticated app that writes files is reachable from every page the
  browser opens. Two checks, both before any route:
  - **Host allow-list against DNS rebinding.** Loopback names, plus the `--host`
    the server was started with. Compare canonically via `ipaddress` (IPv6
    bracketed in `Host`). Verify threw userinfo, trailing dot, `0x7f.1`, `127.1`,
    octal/decimal forms, `[::ffff:127.0.0.1]`, `[::1%lo]` and bad ports at it; all
    rejected.
  - **Origin against CSRF.** `Origin`, if present, must equal the request's own
    origin; else `Sec-Fetch-Site`, if present, must be `same-origin` or `none`.
    Clients sending neither (curl) are allowed.
- **Wildcard binds don't work with a Host check.** No client sends `0.0.0.0` as
  `Host`, so a wildcard bind 400s everyone. `serve` now refuses `0.0.0.0` / `::`
  and asks for a concrete address. Gap left: `--host 0` (V1) — `ipaddress` rejects
  `'0'`, but `getaddrinfo` binds it as 0.0.0.0.
- Port in use: probe the socket once before the banner, one-line error, exit 1.
  A small race remains between probe and bind; accepted.
- Autoescape everywhere; links only from validated ids; the channel's free-text
  `url` is shown, not linked.

## Packaging and tooling

- `packages = ["src/happytube"]` in hatchling already puts templates and static
  files into the wheel. QA proved it by serving from an installed wheel in `/tmp`.
  Templates are found by `Path(__file__)`, not cwd.
- deptry: `python-multipart` is DEP002 (FastAPI loads it for `Form()`, nothing
  imports it); `starlette` is DEP003 (transitive via fastapi, imported for the 404
  handler). Both justified, review agreed.
- vulture: `@app.get` / `@app.post` / `@app.middleware` / `@app.exception_handler`
  added to `ignore_decorators`; `QueueSections` fields (read only by templates) to
  `ignore_names`. The ignore list keeps growing; a whitelist file is backlog.

## Product learnings

- The queue order from context.md looked right in the browser (QA): channels with
  vet flags or unresolved (ct-decko, inactive smithsonian-channel) come first.
- The detail page shows everything a human needs for one decision: "resolved to"
  title, thumbnails, the vet table and every review.
- Web and CLI reviews are the same record. Concurrent writes from both landed as
  separate files (`-2`/`-3`); status derivation didn't change.

## Deferred backlog

- **V1**: `serve --host 0` isn't caught as a wildcard.
- **Q3** (preexisting): installed wheel's default `--channels-dir` resolves inside
  the venv and is silently empty (plan backlog `data_root`).
- Names sort without diacritic awareness (ČT sorts with C). Not worth ICU for ~15
  rows.
- One broken registry file makes the whole queue a 500 (same as `channels list`).
- vulture whitelist file instead of a growing `ignore_names`.
