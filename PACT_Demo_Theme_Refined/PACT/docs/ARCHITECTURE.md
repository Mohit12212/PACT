# Architecture and design decisions

## System overview
The browser SPA communicates with FastAPI JSON endpoints. The API owns authentication, permissions and workflow rules; the browser must not be treated as a security boundary. SQLAlchemy persists users, organisations, listings, partnerships, milestones, messages, metrics, reviews, notifications, settings and audit events. Optional AI calls are routed through an OpenAI-compatible client, with built-in fallbacks for selected operations.

## Boundaries
- **Presentation:** `static/index.html`, `static/styles.css`, `static/app.js`.
- **HTTP/API:** `app/routers/`.
- **Domain and persistence:** `app/models.py`, `app/db.py`, `app/deps.py`.
- **Decision services:** `app/services/matching.py`, `vectors.py`, `sdg.py`, `llm.py`.
- **Runtime operations:** `app/config.py`, `app/main.py`, Docker files and CI.

## Key domain invariants
- Only authenticated users can access organisation workflows.
- Partnership detail is scoped to one of the two participating organisations.
- Only the receiving organisation can accept a new proposal into negotiation.
- Partnership status transitions are server-side validated.
- Reviews are allowed only after completion and once per organisation.
- Admin endpoints require an administrator role.

## Data flow for a match
1. An organisation publishes a structured need or offer.
2. The service uses a configured embedding model when available; a local deterministic vector fallback is available otherwise.
3. Candidate needs/offers are scored across semantic fit, SDG overlap, geography, trust signals and reciprocity.
4. The API returns the overall score, component breakdown and candidate organisation context.
5. Users review the result and decide whether to draft outreach or propose a collaboration.

## Operational constraints
The current rate limiter and real-time hub are process-local. They are suitable for a single-process demonstration, not horizontal scale. The default SQLite database is suitable for local evaluation; use PostgreSQL and migrations for a multi-user deployment. The first-run schema creation is convenient for a demo but should be replaced with controlled migrations in a deployed environment.
