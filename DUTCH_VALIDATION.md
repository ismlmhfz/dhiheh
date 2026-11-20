# Dutch reimplementation — validation status

Full-stack reimplementation of Dutch to `RULES_DUTCH.md`, inside the existing
isolation boundary. The 10 Card Club game, its engine, service, consumer,
templates, styles and tests are unchanged. No production deploy.

## Automated tests — green

`python manage.py test` (SQLite, Python 3.14 + Django 5.2):

- **118 passed, 3 skipped** (the PostgreSQL row-lock concurrency tests skip on SQLite).
- Baseline before the rewrite was 95 tests; the suite grew with new Dutch coverage.
- All pre-existing **10 Card Club tests still pass**, confirming the isolation boundary held.

New / rewritten Dutch suites:

- `game/test_dutch_rules.py` (11) — config validation: ranges, types, unknown-key rejection, frozen copies, flipped tie/failed-cut defaults, enum guards.
- `game/test_dutch_engine.py` (26) — setup/chooser rotation/reveal 0–4, starting peek + timeout auto-pick, 30 s turn timer (skip before draw, auto-discard-no-power after), draw+swap / take-discard, Jack/Queen/King powers incl. locked-card and Dutch-caller guards, event-based single cut (success takes turn, failed cut penalty + 2 s public reveal + turn unchanged, empty-hand ends round), Dutch final order, **tie-fails** 2× and strict-lowest 0, 10th-round match end, card conservation, projection privacy.
- `game/test_dutch_service.py` (17) — lobby/host/dedup, start→choose_reveal flow, idempotent draw + 3 s preview expiry on resync, **no-pause** on disconnect, **all-idle abandon** after a full turn cycle, long-absence abandon on return, chat/isolation/CSRF/poll/watch projection, invite expiry, rematch resets scores.
- `game/test_dutch_ws.py` (2) — real Channels consumers: private timers, per-seat redaction (no `cards`/`draw_pile`/`commands`, opponent faces `null`), spectator action rejection, chat, reconnect hides expired peeks.
- `game/test_dutch_concurrency.py` (3, PostgreSQL only) — single-claim cut race, duplicate-draw dedup, racing swaps; updated to the new single-card cut API and forced-playing setup.

Other checks run here: `GET /dutch/` renders 200 with the new rules config and UI
elements embedded; `node --check static/dutch/dutch.js` passes; no dangling
references to removed dialogs/fields remain in the client.

## Browser scripts — rewritten for the new flow (need a browser to run)

`tests/dutch_browser.py`, `tests/dutch_browser_edges.py`, `tests/dutch_browser_reconnect.py`
and `tests/dutch_fixture.py` have been **rewritten** for the current rules and UI:
rotating chooser pick, synchronized blind-select → shared 3 s reveal, draw-enters-leftmost
(tap a card to discard), **double-tap-to-cut**, single/failed/empty-hand cut, King-lock via
draw+discard, N−1 Dutch final turns, 10-round scoreboard and rematch. They are
syntax-valid but **have not been executed here** (no Playwright/browser in this environment)
— run them against an isolated dev server to confirm.

```bash
DUTCH_BASE_URL=http://127.0.0.1:8097 python tests/dutch_browser.py
```

## Still needs a human: manual multi-browser playthrough

Open 2–6 browser profiles and play a full match. The engine/service paths are
unit/integration-tested, but the **live browser interactions and animations are not yet
exercised by a person.**

## How to validate interactively

```bash
.venv/Scripts/python manage.py runserver 127.0.0.1:8000
# open http://127.0.0.1:8000/dutch/ in 2+ browser profiles, create + join a table
```

Report any UI issue found and it can be fixed against this build.
