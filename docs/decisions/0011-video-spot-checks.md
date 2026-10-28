# 0011 Video spot-checks

Date: 2026-10-28
Status: accepted (amends 0008 and the 0010 selection rule)

## Context

Decision 0008 lets agents gate every video of an approved channel and keeps humans
for spot-checks that measure the agent, but there was nowhere to record one. Phase
5b put real trusted videos on the player, so a human who watches one and finds it
unsuitable needs a way to say so — and that video must leave the player she
watches, not wait for a rubric change.

## Decision

- **Location:** top-level `video-reviews/<video_id>/<stamp>-<reviewer>[-N].yaml`,
  one file per review, append-only, git-tracked. Separate from `channels/` and from
  `stages/` (stage files are machine output and can be redone; reviews are human
  records). The repo is public, so notes are public; the form and the directory's
  README say so. `video-reviews/README.md` keeps the directory in git.
- **Record** (`VideoReview`, pydantic, unknown keys refused): `reviewer`, `role`
  (`human | agent`), `verdict` (`suitable | unsuitable | unsure`), optional rubric
  `flags`, `watched` (`full | part | title`), `notes`, `created_at` (UTC, `Z`), and
  a snapshot of the agent's call the reviewer compared with, copied from the assess
  file at review time: `agent_suitable`, `rubric_version`, `assessed_at` (the last
  two `null` when that assess file lacked them: a video the player shows is always
  reviewable). The UI refuses a review if the video was rescored since the page
  was loaded. The video
  id is the directory, validated with `is_video_id` before any path is built.
- **Derived, like channel status (0003):** the latest *human* review decides (by
  `created_at`, ties in filename order, so the later write wins). Agent reviews are
  stored but never hide a video and never count in the agreement.
- **Override (amends 0010, selection rule 4):** a video is also not shown when its
  latest human verdict is `unsuitable`, or when one of its review files cannot be
  read (it might be the one saying `unsuitable`; warning names the file).
  `suitable` never shows a video the agent scored unsuitable; `unsure` changes
  nothing. Still one pure `select_videos`, shared by the live route and the export;
  the public JSON is unchanged.
- **Missing directory is an error, not "no reviews":** the export exits 1, `serve`
  warns at start and `/player/videos.json` and `/videos` fail (500). A wrong path in
  CI must not silently show a video a human hid. `--video-reviews-dir` /
  `HAPPYTUBE_VIDEO_REVIEWS_DIR`, default `video-reviews/` at the repo root, on
  `serve`, the export and `happytube videos`.
- **Queue:** every assessed trusted video. Unreviewed videos the player shows now
  first (false positives hurt her), then the other unreviewed (agent misses, for
  tuning), then the reviewed (unreadable, disagreements, newest). "Shown" is
  `select_videos` itself. A review directory without an assess file is ignored.
- **Agreement:** latest human verdict against the snapshot's `agent_suitable` (not
  today's assess file — `trusted assess --force` may have rescored it since; the
  detail page shows both and marks "rescored since"). Rate = agreeing decisive
  verdicts / all decisive; `unsure` is counted apart.
- **Where:** review UI `/videos`, `/videos/{id}`, `POST /videos/{id}/reviews`
  (always `role: human`, behind the same Host/Origin guard); CLI `happytube videos
  list | show | review | stats` (no API keys). Shared code: `trusted/video_reviews.py`
  (model, store, derived state, agreement) and `trusted/spot_checks.py` (queue);
  file naming and collision handling shared with the channel registry in
  `happytube/records.py`.
- **Deploy:** `video-reviews/**` is in the Pages push trigger. `scripts/daily_run.sh`
  does not commit `video-reviews/` — the human commits their reviews, as with
  channel reviews.

## Consequences

- A human "unsuitable" takes a video off the local player on the next request and
  off Pages on the next deploy after it is pushed.
- Spot-checks give the agent a measured accuracy over time, per rubric version.
- The agent's verdict stays the gate: a human `suitable` cannot override an agent
  `unsuitable` (rescoring is the way, out of scope here).
- A broken review file hides its video until fixed — safe, but visible: the queue
  marks it "unreadable review".
- Not in scope: rubric changes, rescoring, sampling which videos to check, a
  grandma-facing UI.
