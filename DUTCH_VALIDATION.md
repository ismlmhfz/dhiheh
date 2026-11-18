# Dutch implementation validation

Implemented separately from 10. No production files, database, service, proxy or
certificate configuration were changed. The live site was not deployed/restarted.

## Automated verification

- Baseline before changes: all **59 existing Django tests passed**.
- Integrated PostgreSQL suite: **92 tests passed**, including the original 59,
  engine/service/socket tests and three real database-lock concurrency tests.
- Final targeted PostgreSQL run after additional edge coverage: **36 Dutch tests
  passed**. This includes three additional cases: a final swap overtaking a Dutch
  caller, a shared match win with no eleventh round, and initial-peek timeout/
  foreign-slot rejection.
- Chromium: **six players, ten complete rounds**, final scoreboard, rematch;
  no JavaScript exceptions or page-width overflow at 320px.
- WebKit: **two players, ten complete rounds**, final scoreboard, rematch;
  no JavaScript exceptions or page-width overflow at 320px.
- Firefox: deterministic UI checks passed for three matching cards in one cut,
  a mixed-rank batch receiving exactly one hidden penalty, a private one-second
  Jack peek, and a last-card Jack cut ending immediately with no final turns.
- Chromium with every WebSocket connection forcibly closed: HTTP fallback passed
  readiness, start, initial peeks, private draw, reload after reveal expiry,
  mandatory swap without another reveal, room chat and automatic chat dismissal.
- Browser matches checked spectator projections, both draw sources, exactly N−1
  final turns, round history and chat. Database tests cover all 2–6 capacities,
  stale/replayed commands, card conservation, CSRF, cross-game routes, private
  snapshots, invitation expiry and disconnect handling.

Browser tests use an isolated SQLite database and localhost Daphne instance.
Concurrency tests use an automatically created/destroyed PostgreSQL test database
and deliberately bypass the per-process mutex, exercising row locks directly.
Playwright WebKit validates the WebKit engine, not a physical iPhone/Safari device.

## Review and later deployment

- Rules awaiting owner confirmation are labelled in the in-game rules dialog and
  centralized in `game/dutch_rules.py`; the original specification is preserved
  in `DUTCH_IMPLEMENTATION.md`.
- Existing 10 engine/service/consumer/game JS/CSS are unchanged. Integration adds
  a navigation link, Dutch routes, a cross-game boundary guard and the correct
  admin spectator link for Dutch rooms.
- No schema migration is required. Shared PostgreSQL/Redis are used by the existing
  production configuration; use a shared Django cache for aggregate HTTP rate
  limits when running multiple HTTP workers.
- Dutch bots, voice/video and native group-match creation are optional future
  work, not part of this human-multiplayer milestone.
- Production deployment is intentionally excluded by the supplied specification.
