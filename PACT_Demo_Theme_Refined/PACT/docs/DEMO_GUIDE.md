# PACT Demo Guide

All seed records are fictional and exist solely for product demonstrations and testing.

## Demo credentials
- Main organisation: `demo@partnerhub.dev` / `Demo@12345`
- Technology startup: `techbridge@demo.dev` / `Demo@12345`
- Administrator: `admin@partnerhub.dev` / `Admin@12345`

The admin account is created from `ADMIN_EMAIL` and `ADMIN_PASSWORD`. If you change those values after the first account has been created, the existing password is not automatically reset.

## Dataset contents
On first launch with `SEED_DEMO=1`, PACT creates a network of organisations, structured needs and offers, partnerships in proposed/negotiating/active/completed stages, milestone progress, impact metrics, sample messages, and completed-partnership reviews. It uses deterministic random seeding to keep generated dates repeatable. Values are illustrative and must not be presented as independently verified sustainability outcomes.

## Reset the local demo
1. Stop the server.
2. Back up `pact.db` if you need anything in it.
3. Delete only the local demo database file `pact.db`.
4. Start the server again with `SEED_DEMO=1`.

Do not reset a database that contains real user data.

## Theme controls
The top-bar theme control switches light/dark mode. The selected mode is stored in browser local storage. With no saved preference, the operating system setting is used.
