# 0006 Web stack: FastAPI + htmx

Date: 2026-10-28
Status: accepted

## Context

Decision 0002 put the human review page "in the existing Flask app". The user's
current standard for web work is FastAPI with htmx. The Flask app today is only the
legacy player (`web/server.py`) plus a static export, and it reads legacy data that
nothing writes any more (phase 5 rewires it anyway).

## Decision

- New web code uses **FastAPI + Jinja2 templates + htmx**: server-rendered HTML,
  htmx for partial updates (review form, queue filters), no SPA and no JS build step.
- Phase 4 builds the review UI as a FastAPI app over `ChannelStore` (same review
  records as the CLI, decision 0002 otherwise unchanged).
- The Flask player moves to the FastAPI app when phase 5 rewires it to `stages/`;
  then `flask` is dropped. The static GitHub Pages export stays.
- Supersedes only the "existing Flask app" line of 0002.

## Consequences

- One web stack; FastAPI's typed routes and pydantic models match the registry
  models; TestClient makes routes testable without a server.
- Two web frameworks coexist until phase 5.
- Adds `fastapi`, `uvicorn`, `python-multipart` (forms); `jinja2` is already there.
