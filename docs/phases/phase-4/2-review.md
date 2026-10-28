# Phase 4 — review (report only)

See [context.md](./context.md) — required reading. Also [log.md](./log.md) (dev report).

## Scope
Commit range `06185d1..phase-4-review-ui`. Own worktree:
`git worktree add --detach /tmp/claude-1000/p4-review phase-4-review-ui`, cd there,
`uv sync`. Remove + prune at the end.

## Task
1. Invoke the `python-review` skill (Skill tool) over that range.
2. Logic judgement (QA covers runtime/browser; don't duplicate):
   - Queue sort matches context.md exactly (sections, attention = vet flags or
     unresolved via `channel_flags`, verdict order, name); reused, not
     reimplemented. Is diacritic-blind name sort worth fixing (ČT / Zoo Zlín)?
   - Review POST builds the same `Review` as the CLI (`role: human`), only via
     `store.add_review`; validation path; nothing written on any error.
   - Safety: Host allow-list (incl. `bind_host`, IPv6 `[::1]`, ports), Origin /
     Sec-Fetch-Site logic — any bypass (e.g. `Origin: null`, missing both headers,
     case, trailing slash)? Applies to every state-changing route?
   - Escaping: autoescape on every template incl. partials; links only from
     validated ids; no `|safe` on untrusted text.
   - htmx: OOB badge swap, `responseHandling` config for 422 — correct for htmx
     2.0.11 (read the vendored source)? `Vary: HX-Request` / history restore.
   - Error handling: 404 vs 500 mapping; no traceback or path outside registry
     leaked beyond the store's message.
   - Packaging/tooling: deptry and vulture ignores — justified or masking?
   - Docs (0007, CLAUDE.md, architecture.md) match code.
3. Judge each dev `deviation` and `unresolved_issue` in log.md: accept, or finding.
4. Reproduce where cheap (TestClient, temp channels dir).
5. Number findings R1, R2…; pre-existing issues in untouched code → `preexisting`.

## Constraints
Read-only. Do NOT edit or commit on the branch.

## Report
Return ONLY JSON (≤500 words):
{"findings": [{"id": "R1", "severity": "high|medium|low", "file": "", "issue": "", "fix": ""}],
 "deviations_judged": [{"deviation": "", "ruling": "accept|finding Rn"}],
 "preexisting": [""], "verdict": "ship|fix-first"}
