# Release checklist

## Before a college demo
- [ ] Start from a clean virtual environment and install requirements.
- [ ] Set up `.env`; confirm demo data is appropriate for the demonstration.
- [ ] Run `python -m pytest -q` and `node --check static/app.js`.
- [ ] Test registration, sign-in, organisation editing, listing creation, matching, proposal lifecycle, milestones, messaging, metrics, CSV export and sign-out in a browser.
- [ ] Test narrow/mobile layout and keyboard-only navigation.
- [ ] Explain that trust and impact metrics are platform/user-reported signals, not independent verification.
- [ ] Have a backup of the demo database and a repeatable reset procedure.

## Before public deployment
- [ ] Replace all demo/default credentials and generate a strong unique `SECRET_KEY`.
- [ ] Set `SEED_DEMO=0`; remove test accounts and sample records.
- [ ] Use HTTPS and a correctly configured reverse proxy; review host/origin/CORS policy.
- [ ] Use PostgreSQL, Alembic migrations, automated backups and a tested restore procedure.
- [ ] Add password reset, email verification, MFA for admins and token revocation/session management.
- [ ] Move rate limiting and WebSocket fan-out to shared infrastructure.
- [ ] Audit dependency vulnerabilities and run static/dynamic security tests.
- [ ] Add structured logs, monitoring, error alerting, privacy/retention controls and incident response procedures.
- [ ] Review model-provider privacy, data minimisation and API-key storage.
- [ ] Add evidence provenance and human review before calling impact metrics verified.
- [ ] Run end-to-end, accessibility, load and recovery tests.
