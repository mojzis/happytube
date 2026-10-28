# Phase 4 — fix

See [context.md](./context.md) and [log.md](./log.md) (review R1–R7, QA Q1–Q4).

## Where
Main checkout `/home/matous/git/happytube`, branch `phase-4-review-ui`. First commit
`docs/phases/phase-4/` as-is. Small commits; `uv run poe typecheck` before each;
hooks must pass. Don't push.

## Must fix
- **R1** — htmx requests that get 400/403/404/500 must show the error. Preferred:
  an `htmx:responseError` (or `responseHandling` swap) that puts the server's
  error message into a `role="alert"` region near the form / table; the server
  error page stays the same for plain requests. Test the server side (status +
  message body for HX-Request) and keep the JS a few lines.
- **R2 (Q2)** — `serve` refuses wildcard binds (`0.0.0.0`, `::`) with a clear
  message: "bind a concrete address (e.g. your LAN IP); there is no auth".
  Non-loopback concrete IPv4/IPv6 `--host` works: parse with `ipaddress`, bracket
  IPv6 for the Host check. Fix the test that locks in 0.0.0.0; update 0007.
- **R3** — routes doing file I/O become plain `def`.
- **R4** — `FormError(ValueError)` instead of str-in-union; `parse_filters` with
  explicit params.
- **R5** — import `uvicorn` / `create_app` inside `serve()`.
- **R6** — test names/splits/missing asserts as listed.
- **R7** — `http.HTTPStatus`; human/agent counts from a `ChannelEntry` property
  (also use it in `summary_dict`), not Jinja.
- **Q1** — port in use: no banner before bind fails, or a one-line friendly error
  and exit ≠ 0 (pick one; probing the socket first is fine, say which in
  deviations).
- **Q4** — queue tables share column widths (one CSS rule, `table-layout:fixed` or
  colgroup).

## Do NOT fix (deferred to backlog)
- Q3 / default registry dir outside a checkout (plan backlog `data_root`).
- Diacritic-aware sort; whole-queue 500 on a broken file; vulture whitelist file.

## Finish
`uv run poe check` green.

## Report
Return ONLY JSON (≤400 words):
{"commits": ["sha subject"], "fixed": [{"id": "R1", "how": ""}],
 "tests": "N passed, coverage X%", "deviations": [""], "unresolved_issues": [""]}
