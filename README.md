# whyzainab.blog — 10 Card Club

Source code for https://whyzainab.blog: a Django/Channels multiplayer card game with private tables, team play, bots, room chat, friends and group conversations, spectators, and WebRTC voice with live effects.

## Local development

Requires Python 3.12 or newer.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000. Use separate browser profiles for separate players, or start a solo game with bots. SQLite and an in-memory Channels layer are local defaults.

```sh
python manage.py test
```

## Production

Use `DJANGO_SETTINGS_MODULE=ten.production`, `TEN_DEBUG=0`, a unique `SECRET_KEY`, your `ALLOWED_HOSTS`, PostgreSQL (`DATABASE_URL`) and Redis (`REDIS_URL`). See `.env.example` for variable names; environment files are not automatically loaded by Django.

Run migrations, collect static files, and serve `ten.asgi:application` with Daphne behind an HTTPS reverse proxy. The proxy must support WebSockets. Keep other sites and services isolated.

Voice needs a dedicated coturn relay configured with the same `TURN_SHARED_SECRET` and URLs from `TURN_RELAY_URLS`. Credentials are generated temporarily for seated players. Use a trusted full certificate chain for TLS relay. The live site uses a dedicated ZeroSSL/USERTrust-compatible relay certificate after Linux WebKit rejected the Let's Encrypt chain; website HTTPS is separate. Keep certificate renewal automated.

Production secrets, databases, player data, logs, backups, and TLS private keys are intentionally excluded. Configure them separately on the deployment host. This repository is a source snapshot; pushing commits does not deploy the live site.

## Dutch (separate game)

Open `/dutch/` for 2–6 player tables; players use `/dutch/room/CODE/`, spectators
use `/dutch/watch/CODE/`. The updated rules are documented in `RULES_DUTCH.md`:
rotating reveal chooser, simultaneous starting peeks, 30-second turns, a drawn
card entering the leftmost slot with a three-second private reveal, optional
discard of that draw, Jack/Queen/King powers, double-tap cuts and ten-round scores.
Configuration is centralized in `game/dutch_rules.py`, frozen when a table is
created. Room chat, safe spectators and HTTP reconnect fallback are included.

GSAP 3.13.0 is served locally from `static/dutch/vendor/`; its original license
header and package README are retained. `motion.js` animates public game events
with transform/opacity timelines. Flights never contain private draw/peek faces.
Final-card movement finishes before results appear, without delaying server
scoring or extending reveal/turn deadlines. Reduced motion uses short highlights;
resize, hidden tabs and superseding moves clean up transient overlays.

Existing schema-1 Dutch tables retain their original engine, rules and interface
through `dutch_legacy_*` modules and version dispatch. Create a new table for the
updated mechanics. No table data or scores are rewritten during deployment.
The 10 engine, service, consumer and game assets remain unchanged.

### Validation

Run `python manage.py test`. PostgreSQL enables the real row-lock concurrency
checks (skipped on SQLite). Browser scripts require Playwright and an isolated
local Daphne server, with `DUTCH_BASE_URL=http://127.0.0.1:8097`:

- `tests/dutch_browser.py`: complete 6-player Chromium and 2-player WebKit matches.
- `tests/dutch_browser_reconnect.py`: forced WebSocket outage and private expiry.
- `tests/dutch_motion_browser.py`: cut/penalty, Queen/Jack/King, round results,
  GSAP cleanup, privacy and reduced motion in Firefox.

Deterministic fixtures require `DUTCH_DJANGO_PYTHON` and
`DUTCH_FIXTURE_DATABASE_URL`; they refuse any database other than the isolated
`dutch-browser.sqlite3`. Never run fixture tests against production.

Production uses existing PostgreSQL/Redis and static collection, with no schema
migration. A shared Django cache is recommended for aggregate HTTP rate limits
across multiple workers. Dutch voice, bots and native group-match creation are
outside this milestone. Deployments require user authorization; the user
subsequently authorized the initial release and this branch update.
