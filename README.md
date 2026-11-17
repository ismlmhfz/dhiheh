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
