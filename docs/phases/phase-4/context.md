# Phase 4 — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-4-review-ui`, base `06185d1` (main
after PR #10). Plan: `docs/plan.md` (phase 4 row). Principles: `docs/constitution.md`.
Registry: decisions 0002, 0003, 0004, 0005; web stack: 0006. Phase 3 record:
`docs/phases/phase-3/`. Process lessons: `docs/process-learnings.md`.

## Goal

A local web review page where a human works through the channel registry: a queue
that puts the channels needing a human decision first, a detail page with
everything the agents collected (evidence snapshot, vet report, all reviews), and an
approve / reject / unsure form that writes **the same review records** as
`happytube channels review` — through `ChannelStore`, nothing else.

## Decisions settled (user, 2026-10-28)

Record in `docs/decisions/0007-review-ui.md` (accepted).

- **Reviewer identity: a field, remembered.** The form has a reviewer name field,
  prefilled from a cookie (last name used in this browser), else from
  `--reviewer` / env `HAPPYTUBE_REVIEWER`, else empty. Required. Web reviews are
  always `role: human` (agents use the CLI).
- **Channels only.** No video review queue in phase 4. The vet's per-video scores
  are shown read-only on the detail page. Video review records → phase 5.
- **Local only.** `uvicorn` on `127.0.0.1`, no auth. The app writes files into the
  registry dir; the user commits/pushes. The app runs no git commands.
- **Location:** new package `src/happytube/review/` (FastAPI app factory,
  templates, static). CLI entry `happytube serve`. Legacy Flask `web/` untouched
  (phase 5 ports it).

## Pages and routes

App factory `create_app(store: ChannelStore, *, default_reviewer: str | None) ->
FastAPI` — no module-level app with a global store, so tests build one per tmp dir.

- `GET /` → redirect to `/channels`.
- `GET /channels` — **queue**. Two sections:
  1. *Needs human review* (no human review yet — same rule as
     `filter_entries(needs_human_review=True)`), ordered: attention first (vet
     flags non-empty, or unresolved = no `channel_id` / no evidence), then latest
     vet verdict `unsure` → `reject` → `approve` → not vetted, then name.
  2. *Reviewed*, ordered by status (`candidate`, `approved`, `rejected`), then name.
  Row: name (link), slug, kind, languages, status badge, latest vet verdict +
  flags, suitable/scored (e.g. `39/50`), human/agent review counts. Filters
  status / kind / language as query params (reuse `filter_entries`); the filter
  form uses htmx (`hx-get`, swap the table partial, `hx-push-url`), and works as a
  plain GET without JS. Put the sort in a pure function (`queue_sections` or
  similar) next to the app, tested on its own.
- `GET /channels/{slug}` — **detail**:
  - Channel: name, slug, kind, languages, handle, channel_id, url, notes, added
    by/at, status badge. Link to `https://www.youtube.com/channel/<id>` if known.
  - Evidence (latest snapshot): "resolved to" title (prominent — decision 0004
    look-alikes), custom_url, country, subscribers, video count, fetched_at,
    long-form / Shorts counts, newest upload date. None → "no evidence yet".
  - Vet (latest report): final verdict, model verdict, flags, identity match +
    note, channel calm/happy, summary, concerns, video table (thumbnail
    `https://i.ytimg.com/vi/<id>/mqdefault.jpg`, title linked to
    `https://www.youtube.com/watch?v=<id>`, calm, happy, flags, suitable, note),
    shorts skipped, vet file path. Render from the frontmatter (`VetReport`), not
    the markdown body — no markdown dependency. None → "not vetted".
  - Reviews: all, newest first, human and agent visually distinct; role, reviewer,
    verdict, notes, created_at.
  - Review form (below).
- `POST /channels/{slug}/reviews` — form fields `reviewer`, `verdict`
  (`approve|reject|unsure`), `notes` (optional). Builds `Review(role="human", …)`
  with the same model validation as the CLI and calls `store.add_review`.
  - htmx request (`HX-Request` header): respond with the updated reviews partial
    plus the status badge as an out-of-band swap; form cleared except reviewer.
  - Plain form post: `303` redirect to the detail page.
  - Sets the reviewer cookie (`SameSite=Strict`, `HttpOnly`, path `/`, ~1 year).
  - Invalid input (empty reviewer, unknown verdict): `422` with the form partial
    showing the error and the entered values; nothing written.
- Unknown or invalid slug (`ChannelNotFoundError`) → `404` page. Other
  `ChannelStoreError` (broken file) → `500` page showing the store's message
  (it names the file; it never contains secrets). No tracebacks in responses.

## Safety (local, no auth)

A local unauthenticated app that writes files is reachable from any web page the
user visits (CSRF, DNS rebinding). Required, tested:

- `Host` header must be `127.0.0.1`, `localhost` or `[::1]` (any port) unless the
  server was started with a non-loopback `--host`, in which case also that host;
  else `400`. Blocks DNS rebinding.
- On `POST`: `Origin` header, if present, must equal the request's own origin;
  if absent, `Sec-Fetch-Site` (if present) must be `same-origin` or `none`; else
  `403`, nothing written.
- `serve --host` other than loopback prints a warning (no auth!) but is allowed.
- Jinja autoescape on for all templates; notes, names, titles, descriptions from
  YouTube are untrusted text. Links built only from validated ids
  (`CHANNEL_ID_PATTERN`, video ids from the snapshot).
- No external JS/CSS: **vendor htmx** (latest 2.x, minified) into
  `review/static/`, with version and source URL in a comment at the top and in
  0007. Thumbnails from `i.ytimg.com` are the only external requests.

## CLI

`happytube serve [--host 127.0.0.1] [--port 8000] [--channels-dir PATH]
[--reviewer NAME]` — top-level command (not under `channels`). `--channels-dir`
same default and env (`HAPPYTUBE_CHANNELS_DIR`) as the `channels` group — share
the option definition, don't copy it. `--reviewer` env `HAPPYTUBE_REVIEWER`.
Prints the URL; runs `uvicorn.run(create_app(...), host=…, port=…)`. Needs no API
keys. A missing registry dir: start anyway, queue shows "no channels".

## Code shape

- `happytube/review/__init__.py`, `app.py` (factory, routes, host/origin
  middleware or dependency), `queue.py` (pure sort/sections), `templates/`
  (`base.html`, `queue.html`, `_queue_table.html`, `channel.html`,
  `_reviews.html`, `_review_form.html`, `error.html`), `static/` (`htmx.min.js`,
  `review.css`). Templates/static found via package path (`Path(__file__)`), not
  cwd. Make sure hatchling includes them in the wheel.
- The store stays the only reader/writer; no new file formats; no caching layer
  (re-read per request; 15 channels).
- Calm, plain styling: readable font size, high contrast, no framework. One CSS
  file.
- Deps: `fastapi`, `uvicorn`, `python-multipart` (runtime); `httpx` for
  `TestClient` (dev group). `jinja2` already present. `uv add`, pinned with `>=`.

## Tests (no network, no server)

`fastapi.testclient.TestClient` over `create_app(ChannelStore(tmp_path), …)` with
fixture channels (with/without evidence, with/without vet, human/agent reviews,
unresolved, Czech names). Cover: queue order and sections (pure function + one
page test), filters, detail page with each piece present/absent, POST via htmx and
plain (file written, status changes after approve, agent review doesn't change
it), validation 422 writes nothing, cookie set and prefilled, default reviewer
prefilled, 404/invalid slug, broken channel.yaml → 500 with message, escaping
(`<script>` in notes and in a YouTube title rendered escaped), Host check, Origin /
Sec-Fetch-Site check, `serve --help` and option wiring (monkeypatch `uvicorn.run`).

Baseline: 298 tests pass, `poe check` green, coverage 75%. After: `uv run poe
check` green; `uv run poe typecheck` before each commit of a multi-commit step.

## Real run (dev, exploratory, nothing committed)

Copy `channels/` to scratch (`/tmp/claude-1000/-home-matous-git-happytube/<session>/scratchpad/p4-channels`
or similar), start `uv run happytube serve --channels-dir <copy> --port 8765` in
the background, exercise with `curl`: queue, a detail page per kind of channel
(vetted approve, inactive unsure, unresolved ct-decko), a POST review (htmx and
plain), a forged-Origin POST (must be 403), a bad Host (400). Check the review file
landed in the copy only. Stop the server. Report what you saw; nothing from the
copy is committed. No API keys are involved.

## Docs

- `docs/decisions/0007-review-ui.md` (accepted): the four settled decisions,
  safety rules, htmx vendored version.
- CLAUDE.md: `happytube serve` under commands, `review/` in key modules and the
  storage/web tree, note that the review UI needs no keys and writes into the
  registry like the CLI.
- `docs/architecture.md`: the review app.
- Don't touch `docs/plan.md`, `docs/next-session.md`, `docs/phases/` (except
  committing `docs/phases/phase-4/` as-is first).

## Existing code to know

- `channels/store.py`: `ChannelStore` (`entries`, `get`, `add_review`),
  `ChannelEntry` (`status`, `has_human_review`, `latest_evidence`, `latest_vet`,
  `summary_dict`, `detail_dict`), `StoredVet`, `filter_entries`, `derive_status`,
  `ChannelStoreError`, `ChannelNotFoundError`.
- `channels/models.py`: `Channel`, `Review`, `Evidence`, `EvidenceVideo`,
  `VetReport`, `VetVideo`, `VERDICTS`, `KINDS`, `LANGUAGES`, `CHANNEL_ID_PATTERN`.
- `channels/vet.py`: `long_form`, `channel_flags` (unresolved/inactive logic —
  reuse for "attention", don't reimplement).
- `cli/channels.py`: `channels` group with `--channels-dir`; `review_channel`
  shows how a CLI review is built. `cli/commands.py`: top-level `cli`.
- `paths.py`: `PROJECT_ROOT`.

## Tooling gotchas

- Parallel agents: own worktree via `git worktree add --detach <path>
  phase-4-review-ui`, `uv sync` there, remove + prune after.
- Don't run pytest concurrently in one checkout (shared `.coverage`).
- madoqua hook on staged .py only; never `--no-verify` / `MADOQUA_SKIP`.
- Staged-only `ty` misses cross-file breakage: `uv run poe typecheck` per commit.
- `tyf` index stale after hook reformat: `uv run tyf daemon restart`.
- Click group options go before the subcommand (`happytube channels
  --channels-dir X list`); `serve` is top-level so its options follow it.
- Background servers: kill them before finishing; check the port is free.
