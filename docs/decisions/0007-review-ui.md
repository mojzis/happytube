# 0007 Local review UI for the channel registry

Date: 2026-10-28
Status: accepted

## Context

Phases 1–3 fill the registry with candidates, evidence snapshots and agent vet
reports, but a human decision still means reading YAML and markdown and typing
`happytube channels review …`. Phase 4 adds a web page for that decision, on the
stack chosen in 0006, writing the same review records as the CLI (0002, 0003).

## Decision

- **Reviewer identity: a field, remembered.** The review form has a required
  reviewer name, prefilled from a cookie (the last name used in this browser), else
  from `serve --reviewer` / `HAPPYTUBE_REVIEWER`, else empty. Web reviews are always
  `role: human`; agents use the CLI.
- **Channels only.** No video review queue in phase 4; the vet's per-video scores are
  shown read-only on the channel page. Video review records come in phase 5.
- **Local only.** `happytube serve` runs uvicorn on `127.0.0.1` with no auth. The app
  writes review files into the registry directory through `ChannelStore` (no new
  file format, no cache, re-read per request); the user commits and pushes. The app
  runs no git commands and needs no API keys.
- **Location.** Package `src/happytube/review/` (FastAPI app factory
  `create_app(store, *, default_reviewer, bind_host=None)`, templates, static), CLI
  `happytube serve`. The legacy Flask `web/` stays untouched until phase 5 ports it.

Pages: `/channels` is the queue — *needs human review* (no human review yet) with
attention first (vet flags, or unresolved: no `channel_id` / no evidence), then latest
vet verdict `unsure` → `reject` → `approve` → not vetted, then name; then *reviewed*,
by status (candidate, approved, rejected), then name; status / kind / language
filters. `/channels/<slug>` shows the channel, the latest evidence ("resolved to"
title prominent, 0004), the latest vet from its frontmatter, all reviews newest first
and the form. `POST /channels/<slug>/reviews` validates like the CLI; htmx gets the
reviews section back with the status badge swapped out-of-band, a plain form post a
303 to the page; invalid input is a 422 with the form and nothing written.

### Safety rules

A local unauthenticated app that writes files is reachable from any page the user's
browser visits, so:

- **Host check (DNS rebinding):** the `Host` header must be `127.0.0.1`, `localhost`
  or `[::1]` (any port), or the `--host` the server was started with (a name, IPv4
  or IPv6 address — compared canonically via `ipaddress`, IPv6 bracketed in `Host`);
  else `400`.
- **Origin check (CSRF):** on every non-GET request an `Origin` header, if present,
  must equal the request's own origin; if absent, `Sec-Fetch-Site`, if present, must
  be `same-origin` or `none`; else `403`. Both checks run before any route, so a
  refused request writes nothing. Clients sending neither (curl) are allowed.
- `serve --host` other than loopback prints a no-auth warning but is allowed. A
  wildcard bind (`0.0.0.0`, `::`) is refused — no client sends it as `Host`, so it
  could only 400 everyone: "bind a concrete address (e.g. your LAN IP); there is no
  auth". A port already in use is a one-line error (the port is probed once before
  the banner) and exit 1.
- Jinja autoescape on for every template: names, notes, titles and descriptions are
  untrusted. Links are built only from validated ids (`CHANNEL_ID_PATTERN`; video ids
  matching `[A-Za-z0-9_-]+`); the channel's free-text `url` is shown, not linked.
- No external JS or CSS: **htmx 2.0.11** is vendored as
  `review/static/htmx.min.js` from
  <https://unpkg.com/htmx.org@2.0.11/dist/htmx.min.js> (npm `htmx.org@2.0.11`,
  BSD-2-Clause; sha256 of the upstream file
  `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717`). Thumbnails
  from `i.ytimg.com` are the only external requests.
- The reviewer cookie is `HttpOnly`, `SameSite=Strict`, path `/`, one year.
- Store errors render as pages: unknown or invalid slug `404`, a broken file `500`
  with the store's message (it names the file); never a traceback. To an htmx
  request any error (400 / 403 / 404 / 500) is the message as plain text, which
  `review/static/review.js` puts (as text) into the page's `role="alert"` region —
  htmx itself swaps nothing on an error; 422 form errors swap the form as before.

## Consequences

- A human decision is a click on a page that shows everything the agents collected;
  the record is identical to a CLI review, so status derivation (0003) is unchanged.
- Committing the new review files stays a manual step; nothing is pushed by the app.
- One broken registry file makes the queue page a 500 (the store refuses to hide it),
  like `channels list`.
- Serving on a non-loopback address is possible but unauthenticated; anyone who can
  reach it can write reviews.
- htmx updates are manual: replace the vendored file and its header comment, and
  this record.
