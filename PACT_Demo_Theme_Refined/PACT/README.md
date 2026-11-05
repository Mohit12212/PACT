# PACT — Partnership Intelligence

**PACT is an SDG 17 collaboration operating system** for NGOs, colleges, startups, companies, government bodies and community organisations. It helps them make needs and offers discoverable, identify complementary partners, coordinate delivery, and record outcome metrics.

> This repository is a substantial college/portfolio-ready product foundation, not a claim of production certification. Public launch requires a security review, real-browser end-to-end testing, deployment-specific database migrations/backups, privacy review, and validation of impact evidence.

## Product experience

PACT is organised around the work a partnership must do, rather than around a list of CRUD pages:

1. **Command centre** — key signals, suggested connections, pending collaborations and ecosystem gaps.
2. **Partner intelligence** — ranked matches with a per-signal score breakdown and explain/draft/propose actions.
3. **Opportunity exchange** — search open needs and offers by text, kind and SDG.
4. **Collaboration studio** — a stage-based pipeline and a shared workspace for milestones, messages, metrics and reviews.
5. **Impact observatory** — metrics grouped by SDG, ecosystem coverage, CSV export and AI-assisted narrative draft.
6. **Evidence review** — submit an evidence URL with an outcome metric and let administrators mark the claim verified or rejected with a review note.
6. **Network map** — a visual overview of organisations and current collaboration edges.
7. **Organisation directory and profile** — searchable organisations, trust signals, focus SDGs, needs and offers.
8. **PACT copilot** — contextual partnership planning, with an offline fallback when a model is unavailable.
9. **Trust & governance** — admin verification, account access and audit trail.
10. **AI settings** — connect an OpenAI-compatible model endpoint (e.g. Ollama or LM Studio).

## Demo-ready dataset and theme controls

PACT seeds a fictional demonstration network on the first run when `SEED_DEMO=1`. It includes organisations across NGOs, colleges, startups, companies and community partners; needs and offers; partnership records across multiple lifecycle stages; milestones; impact metrics; reviews; and sample collaboration messages. All organisations and impact values in the seed are illustrative demo data, not claims about real-world organisations.

### Demo accounts

| Purpose | Email | Password |
|---|---|---|
| Main organisation demo | `demo@partnerhub.dev` | `Demo@12345` |
| Technology startup | `techbridge@demo.dev` | `Demo@12345` |
| Administrator | `admin@partnerhub.dev` | `Admin@12345` |

Other seeded organisation accounts use the first word of the organisation name as the email prefix (lowercase) followed by `@demo.dev`, with password `Demo@12345`. If a specific email is not obvious, inspect the seeded organisation names in `app/seed.py`. The administrator email/password are controlled by `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`.

**Existing database note:** seed data is created only when the database has no organisations. If you want a clean demo dataset, stop the app and back up/delete the local `pact.db`, then restart. Do not delete a database containing real or valuable data.

### Light and dark themes

Use the half-circle/sun control in the top bar to switch between light and dark modes. PACT uses a calm, high-contrast sustainability palette: evergreen/navy surfaces for focus, a restrained lime accent for primary actions, and SDG colours only for SDG identifiers. Your choice is saved in browser local storage and restored on the next visit. If no choice has been saved, PACT follows the operating system's colour preference.

### Suggested demo walkthrough

1. Sign in as `demo@partnerhub.dev`.
2. Open **Partner intelligence** and inspect match scores and their component breakdowns.
3. Open **Opportunity exchange** and search for a need such as volunteer support, software, clean energy or water.
4. Open **Collaboration studio** and select a seeded partnership to show milestones, messages and metrics.
5. Open **Impact observatory** to explore illustrative SDG outcomes.
6. Sign out and sign in as the administrator to review trust/governance and evidence review features.
7. Toggle light/dark mode and show that the preference persists after refreshing.

## Technology

- **API:** Python, FastAPI, SQLAlchemy
- **Database:** SQLite by default; PostgreSQL can be configured with a suitable SQLAlchemy driver
- **Authentication:** signed JWT tokens and password hashing
- **Frontend:** accessible responsive SPA using vanilla JavaScript, HTML and CSS; no Node build step required
- **AI:** optional OpenAI-compatible local or hosted model; built-in matching and fallbacks keep core workflows usable without it
- **Testing:** Pytest API/permission/matching tests; JavaScript syntax check in CI
- **Deployment:** Docker and Docker Compose starter configuration

## Quick start — Windows / VS Code

1. Extract the ZIP and open the `PACT` folder in VS Code.
2. In the integrated terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

3. Open **http://127.0.0.1:8000**. API docs are at **http://127.0.0.1:8000/docs**.
4. The first start creates the database schema and (unless `SEED_DEMO=0`) seeds a sample organisation network. Demo accounts are listed below.

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, or run `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` without activating the environment.

### Demo accounts

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@partnerhub.dev` | `Admin@12345` |
| GreenRoots demo organisation | `demo@partnerhub.dev` | `Demo@12345` |
| TechBridge demo organisation | `techbridge@demo.dev` | `Demo@12345` |

These are for a local demonstration only. Never expose a seeded demo environment to the public internet. Set a unique `SECRET_KEY`, unique administrator password, and `SEED_DEMO=0` for a clean deployment. Existing database records are not automatically re-passworded when `.env` changes.

## Run tests

```powershell
python -m pytest -q
node --check static/app.js
```

The automated suite exercises API workflows and core permission/matching behaviour. A passing test suite does **not** replace browser-based testing or a security review.

## Optional local AI

1. Start Ollama or another OpenAI-compatible endpoint.
2. Download a compatible chat model and (optionally) an embedding model.
3. Sign in as administrator → **AI & platform settings**.
4. Enter the base URL and model IDs, save, then test the connection.

For Ollama, a common OpenAI-compatible base URL is `http://localhost:11434/v1`. When PACT runs inside Docker, use `http://host.docker.internal:11434/v1` on supported desktop setups. The API key should be stored in environment/configuration, not committed to source control.

## Existing database upgrade

If you are upgrading an older PartnerHub database, stop the server, back up the database, set `DATABASE_URL` in `.env` to point to that database, then run `python scripts/migrate_impact_evidence.py` before starting the new version. Fresh databases need no migration. This small migration adds evidence URL and review-state fields to impact metrics.

## Architecture

```text
app/
  main.py                 FastAPI app, lifespan, SPA/static serving, WebSocket
  config.py               Environment-backed configuration
  db.py                   SQLAlchemy engine/session/base
  models.py               Organisations, users, listings, partnerships, metrics, messages, audit
  security.py             Password hashing and token helpers
  deps.py                 Authentication dependencies, permissions, serialisers
  routers/
    auth.py               Registration, login, current user
    orgs.py               Organisation profiles and marketplace listings
    matches.py            Partner recommendations and gap analysis
    partnerships.py       Proposals, lifecycle, milestones, messages, impact metrics, reviews
    ai.py                 Model connection and AI-assisted actions
    system.py             Notifications, analytics, exports, admin operations
  services/
    matching.py           Explainable weighted partner matching
    vectors.py            Local semantic-vector fallback
    llm.py                OpenAI-compatible model client
    sdg.py                SDG classification/helpers
    realtime.py           In-process WebSocket notification hub
static/
  index.html              App shell
  styles.css              Design system and responsive layout
  app.js                  Workflow-first SPA and API integration
 tests/                   API, permissions and matching tests
 docs/                    Product, architecture, test and release plans
```

## Matching model

The current engine combines semantic similarity, SDG overlap, geography, trust signals and reciprocity. It exposes the component scores to make recommendations more explainable. These weights are heuristic defaults, not scientifically calibrated predictions. See `docs/PRODUCT_SPEC.md` for evaluation requirements.

## Production-readiness work still required

- Use a database migration tool such as Alembic before changing deployed schemas.
- Move rate limiting and WebSocket fan-out to shared infrastructure for multi-worker deployment.
- Add email verification, password reset, MFA for administrators, and session/token revocation.
- Review CORS, HTTPS/proxy configuration, CSRF assumptions, upload limits, logging and privacy retention.
- Add end-to-end browser tests across desktop/mobile and test accessibility with keyboard/screen readers.
- Add evidence attachments, verification workflow and provenance for impact metrics before publishing public outcome claims.
- Evaluate match relevance with a labelled dataset (precision@k, recall@k and qualitative review).
- Set up managed PostgreSQL, automated backups, restore drills, monitoring and incident response.

See `docs/RELEASE_CHECKLIST.md` before any public deployment.
