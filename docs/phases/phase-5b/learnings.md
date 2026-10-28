# Phase 5b — learnings

Loop: context (3 questions to the user, one call) → dev → review ‖ QA → fix →
combined verify → orchestrator probe. 6 agent steps incl. dev; ~$0.07 Anthropic,
33 YouTube units (dev's real run only).

## Loop design
- **Listing failure scenarios in context.md worked** (5a open question): dev
  designed for all seven, review found no logic gap in the selection, QA's 31
  seeded cases all passed. Findings moved to the edges: the shell script, the
  deploy trigger, serve's silent empty state.
- Review and QA overlapped on 3 of 6 QA findings (R1=Q6, R3=Q2, R4=Q3); QA alone
  found the one medium (Q1, failed push never retried) by running the script
  against a bare remote. Runtime checks of shell glue are worth their own item.
- Verify found only info-level items again. One fix round + verify holds (phases
  0–5b).
- Orchestrator probe reused dev's real scratch data: no paid calls, final code,
  real records. Cheapest probe so far.

## Briefs & context
- Asking the three open choices up front in one question call, each with a
  recommended option, took one round trip; the rest went into "Settled by the
  orchestrator (defaults; dev may argue)". Dev argued none and added stricter
  validation itself.
- The channel-status filter (hide videos of a later-rejected channel) was an
  orchestrator default, not a user question; a safety default the user can
  override is fine to settle in context.
- External one-time steps (enabling Pages) are better done by the orchestrator
  with `gh` when the user asks, then messaged to the running dev so docs match.

## Agent reports
- Dev's `unresolved_issues` named the red-deploy-until-first-data-commit effect;
  it went straight to the user-facing summary.
- Fix agent's deviation (compact date dirs now skipped) closed a 5a backlog item
  (V2) as a side effect; verify confirmed nothing depended on the old behaviour.

## Tooling gotchas
- `pkill -f <pattern>` from the Bash tool matches the tool's own shell → exit
  144. Use `pgrep` + kill by pid, or a pattern that can't match the command line.
- The export's default output is inside the repo (`static/videos.json`); now
  git-ignored, so probes don't dirty the tree.

## Open questions
- Should QA always get a "run the shell glue against a bare remote / stubbed tool"
  item when a phase touches scripts?
- First committed `stages/trusted/` data: who runs it, from which machine, and is
  a daily cron on this machine the intended home?
