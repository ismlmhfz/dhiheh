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

Dutch is available at `/dutch/` with player rooms at `/dutch/room/CODE/` and
safe spectator links at `/dutch/watch/CODE/`. The original 10 game keeps its
engine, service, WebSocket protocol, card interactions and styling. Its only
visible addition is a **Play Dutch** navigation link. Boundary guards reject
cross-game room codes before invoking the original 10 endpoints.

Dutch supports 2–6 guests, full-seat readiness, private timed peeks, mandatory
swaps, atomic multi-card cuts, Jack peeks, Dutch final turns, ten-round cumulative
scoring, rematches and 120-character room chat. Spectators receive public counts,
discards and finished-round scores, never active hands or room chat. Accounts
and friends remain available through the existing site. Dutch voice, bots and
native group-match creation are not included in this milestone.

All unconfirmed rules live in `game/dutch_rules.py:DUTCH_RULES`; override keys in
Django's `settings.DUTCH_RULES` before creating rooms. Each room freezes a copy.
The rules dialog identifies these as engineering defaults awaiting confirmation:
A=1 through K=13; shared random 1–4 starting peeks per match; 3-second initial
reveal; clockwise rotation; a new random starter per round; Dutch instead of your
turn; tied-lowest callers succeed; match ties share the win; 3-second cut windows;
one penalty for a bad batch; failed cutter gets the next turn; chained cuts;
Jack effects on cuts and final swaps; recycle discards except the top. Additional
operational defaults: 30 seconds to select starting peeks, 10 seconds to select a
Jack peek, 90 seconds to reconnect, and reject a penalty if no physical card is
available. Required draw/Jack reveals remain 2/1 seconds, and matches remain ten
rounds. No settings change can enable final-turn cuts or delay an empty-hand win.

The server owns all deadlines. Commands use UUID deduplication plus turn/cut event
checks, inside database row locks. Reveals are removed from every outgoing
projection at expiry, including reconnect snapshots. Slot handles identify
positions, never hidden card identities. Socket leases support multiple tabs;
a polling fallback renews its own lease and uses the same CSRF-protected actions.
Disconnections pause play, without extending reveals; a grace timeout abandons
the unfinished round without awarding points. Timers are resolved on any room
read/action, with connected sockets ticking every 250 ms. A dormant room resolves
expired deadlines when next accessed; it does not require a background worker.

### Validation

Run the existing and new Django suites with `python manage.py test`. The three
row-lock race tests in `game/test_dutch_concurrency.py` run on PostgreSQL and skip
on SQLite. They bypass the process mutex to verify database serialization of
competing cuts, duplicate draws and simultaneous swaps.

For browser checks, start an **isolated development database/server**, install
Playwright in a test environment and run:

```bash
DUTCH_BASE_URL=http://127.0.0.1:8097 python tests/dutch_browser.py
```

This drives complete ten-round matches with six Chromium players and two WebKit
players, including timed peeks, both swap sources, final turns, spectator privacy,
chat, rematches and 320px layouts. Never point test automation at production.

No migration is needed: Dutch uses the existing room JSON and room-chat models.
Production should continue using PostgreSQL and Redis Channels. For multiple
HTTP workers, configure a shared Django cache for aggregate rate limits (the
local-development default is per process). Deploy source/static assets only
through the existing runbook after review; **this implementation does not deploy
or restart the live site**, as requested in `DUTCH_IMPLEMENTATION.md`.

Additional browser checks: `tests/dutch_browser_reconnect.py` forces WebSockets
closed and exercises polling, expired-draw reload and chat. The deterministic
Firefox cut/Jack checks in `tests/dutch_browser_edges.py` require
`DUTCH_DJANGO_PYTHON` and `DUTCH_FIXTURE_DATABASE_URL` pointing to the test Python
and isolated `dutch-browser.sqlite3`; the fixture refuses any other database.
