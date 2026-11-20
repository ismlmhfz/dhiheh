DUTCH — Implementation plan (reimplementation)

Repository: ismlmhfz/dhiheh
Target: Rebuild the Dutch card game end-to-end to match the current `RULES_DUTCH.md`, as a full-stack reimplementation that stays inside the existing isolation boundary and does not touch the 10 Card Club game.

Document status: `RULES_DUTCH.md` is the single source of truth for game rules and table UI. This file is the engineering plan: it does not restate the rules, it says how to build them. Anything marked **[DEFAULT — CONFIRM]** mirrors a default in `RULES_DUTCH.md` and must live in the one configurable rule object, never presented as a confirmed rule.

---

## 1. Mission and integration constraints

Replace the existing Dutch engine, service, consumer, views, templates, styles and tests with a new implementation of the consolidated rules, while keeping the 10 Card Club game byte-for-byte unchanged. This is a rewrite of Dutch behaviour, not of the shared platform.

Hard constraints (unchanged from the current build):
- **Isolation boundary stays.** Dutch rooms are `Room.state['game_type'] == 'dutch'`. Routes live under `/dutch/…`; the WebSocket is `ws/dutch/<code>/`. `dutch_views.TenIsolationMiddleware` and `dutch_consumer.IsolatedTenConsumer` must continue to reject cross-game room codes before any 10 code runs. Do not route `/room/` or `/ws/room/` traffic into Dutch.
- **Shared platform is reused, not forked.** Reuse `Room`, session identity (`service.identity`, `seat_of`, the `@serialized` mutex), the Channels layer, CSRF, login, `chat.py` room chat, and brand/style tokens. Do not import or modify `game/engine.py` or `game/service.py` mutation logic for Dutch gameplay.
- **Server is authoritative.** All cards, deadlines and powers live only in `Room.state`; clients receive an individually redacted projection. Never ship hidden faces and hide them with CSS.
- **No schema migration.** Dutch keeps using the existing `Room` JSON and the room-chat model. `schema_version` in state covers Dutch shape changes.
- **No production deploy** as part of this work.

Files in scope (rewrite):
```
game/dutch_engine.py      # pure rules/state machine — the bulk of the change
game/dutch_rules.py       # the single configurable rule object + validation
game/dutch_service.py     # atomic room lifecycle, presence, action dispatch
game/dutch_consumer.py    # WebSocket routing + per-seat snapshots
game/dutch_views.py       # landing/table/API + isolation middleware (middleware unchanged)
templates/dutch/index.html
static/dutch/dutch.js
static/dutch/dutch.css
game/test_dutch_engine.py
game/test_dutch_service.py
game/test_dutch_ws.py
game/test_dutch_concurrency.py
```
Out of scope for this milestone: Dutch bots, Dutch voice, and native group-match creation (those remain future work; see §15).

**Approach: hybrid, not greenfield.** `dutch_engine.py` and `dutch_rules.py` are rewritten from scratch — the new ruleset diverges too far to patch cleanly. `dutch_service.py`, `dutch_consumer.py`, `dutch_views.py` and the front-end are evolved in place: their platform integration (lobby lifecycle, lease-based presence, atomic `mutate`, per-seat projection plumbing, isolation guards, dialog structure, render loop) is already correct and tested, and re-deriving it would be slower and riskier than extending it.

## 2. What changes from the current build

The current Dutch engine implements an older ruleset. The new rules differ in core mechanics — treat these as the checklist of what to tear out and rebuild:

| Area | Current build | New rules (`RULES_DUTCH.md`) |
|---|---|---|
| Reveal count | Server picks a random shared count 1–4 | **Rotating chooser** seat picks **0–4**; chooser rotates one seat right each round |
| First player | Random starter each round | The **chooser** starts; deterministic rotation |
| Turn timer | None | **30 s** per turn, with skip / auto-discard on timeout |
| Draw preview | 2 s (hard-coded invariant) | **3 s** (configurable) |
| Discard drawn card | Not allowed (forced swap) | **Allowed** — draw then discard straight away |
| Power cards | Jack only, triggered on swap / cut / final | **Jack, Queen, King**, triggered **only** on draw-then-discard-straight-away |
| — Jack | 1 s own-card peek | Same (1 s own-card peek) |
| — Queen | — | **Blind swap**: one own card ↔ one opponent card, neither face seen, slots swap face down |
| — King | — | **Lock / unlock**: lock a card face-up (any hand); locked cards can't move/discard/cut but still score |
| Cut window | 3-second timer | Open **until the next player plays** (event-based); first valid cut wins |
| Multi-card cut | Atomic multi-cut | **Single card** per cut |
| Failed cutter | Takes next turn | Does **not** take the turn; order continues |
| Failed cut reveal | — | Cut card shown **publicly for 2 s**, then face down |
| Dutch tie | Tie wins (caller 0) | Tie **fails** (caller 2×) |
| Disconnect | Pause + 90 s grace → abandon | **No pause**; disconnected turns time out and skip |
| Setup choice timer | 30 s, forfeit unselected | 15 s, auto-pick (chooser→random, peek→nearest cards, bottom row first) |
| Public projection | Counts + top discard only | Also: **replaced slot** on a swap, both slots of a Queen swap, every **locked** card face, every **cut** card (incl. failed, for 2 s) |

Terminology is **"cut"** (matches existing code naming); do not rename to "snap".

**Interaction amendments (owner, post-rewrite):**
- **Draw enters the leftmost slot.** `draw` inserts the drawn card at hand index 0; the player then discards one card — `discard_drawn` discards the drawn card itself (power if J/Q/K), `swap_drawn {slot}` discards a chosen *other* card and keeps the draw at leftmost. Take-from-discard stays position-preserving. This intentionally overrides the "slot positions stay fixed" line in `RULES_DUTCH.md §3.1`.
- **Consolidated setup timers 10 / 10 / 3.** Chooser has 10 s to pick (picking ends it early); everyone then has 10 s to *blind-select* which cards; then all peeks reveal **simultaneously** for 3 s (own-only) before play. `status='initial_peek'` carries `phase='select'` then `phase='reveal'`; `setup_choice_seconds=10`.
- **Cutting is a double-tap** on one of your own cards (no cut button).
- **Animations** surface the drawn card entering leftmost and the discarded card leaving, so opponents can track swaps.

## 3. Domain model and persisted state

One standard 52-card deck, reshuffled per round with a cryptographically secure RNG. Assign a unique opaque id per physical card so duplicate ranks are never ambiguous, and a per-round stable **slot handle** per hand position that is independent of the card identity and survives swaps. A discarded/cut face never carries a hidden id.

Recommended `Room.state` shape (illustrative):
```python
state = {
  "game_type": "dutch",
  "schema_version": 2,
  "status": "lobby",        # lobby | choose_reveal | initial_peek | playing | dutch_final | round_results | match_results | abandoned
  "phase": "lobby",         # fine-grained sub-phase (see §4)
  "host": 0,
  "players": [...],         # 2..6 seats; each seated player has a stable identity + presence leases
  "player_limit": n,
  "round": 0,               # 1..10 while active
  "max_rounds": 10,
  "scores": [0]*n,
  "round_history": [],
  "round_result": None,
  "winner_seats": [],

  "direction": 1,           # turn + chooser rotation direction ("right"), configured, never implied from 10
  "chooser": None,          # seat whose turn it is to pick the reveal count this round
  "reveal_count": None,     # 0..4 once chosen; drives every player's starting-peek count
  "starter": None,          # == chooser for the round
  "turn": None,             # active seat
  "turn_id": 0,             # monotonic; stale turn-scoped actions rejected
  "turn_deadline": None,    # server_now + TurnSeconds; resolved in tick()
  "setup_deadline": None,   # server_now + SetupChoiceSeconds for choose_reveal / initial_peek
  "first_turn_done": [bool]*n,

  "hands": [[{"slot": handle, "card": card_id, "locked": False}, ...], ...],  # private
  "cards": {card_id: {"rank": r, "suit": s}},  # private; server only
  "draw_pile": [card_id, ...],                 # private ordered
  "discard_pile": [card_id, ...],              # top is public

  "initial_peeks": {seat: {owner, cards:[...], until}},   # private timed reveals
  "initial_peeks_done": [bool]*n,
  "reserved": None,         # {owner, seat, card_id, until}  the 3 s drawn-card preview
  "power": None,            # pending/active power: {seat, owner, kind: jack|queen|king, step, until/select_until, ...}
  "cut_window": None,       # {event_id, rank}  open until the next player plays
  "cut_reveal": None,       # {seat, card_id/face, until}  transient public failed-cut reveal (2 s)

  "dutch_caller": None,
  "final_turn_order": [],   # exactly every other seat, once
  "final_turn_index": 0,

  "commands": [],           # bounded idempotency log (who:uuid)
  "revision": 0,
  "created_at": now,
  "invitation_closed": False,
}
```
Notes:
- A hand slot carries `locked`. A locked slot's face is **public** (see §8), cannot be swapped/discarded/cut/Queen-moved, and still counts toward the total.
- A Dutch caller's whole hand is treated as locked for the remainder of the round (no Queen/King/cut/swap can touch it), independent of per-card `locked` flags.
- `power` holds at most one pending power for the active player; it is consumed or expires inside the 30 s turn and never extends it.

## 4. State machine and phases

Per-round flow: **deal → choose_reveal → initial_peek → playing (→ dutch_final) → round_results**, then next round or match_results after round 10.

```
Lobby (2–6 ready)
  → Deal 4 each, flip first discard
  → choose_reveal: chooser picks 0–4 (SetupChoiceSeconds; timeout → random)
  → initial_peek: each player picks exactly reveal_count own cards, 3 s private reveal
                  (SetupChoiceSeconds; timeout → nearest cards, bottom row first; reveal_count 0 → skip)
  → playing: turns rotate right from the chooser, 30 s each
       after every seat's first turn → cutting + Dutch unlock
       empty-hand cut → round ends immediately (cutter 0)
       Dutch called → dutch_final
  → dutch_final: each other seat one normal turn (no cut, no Dutch), caller's hand locked
  → round_results → (round<10 ? next round : match_results)
```

Sub-phases (`phase`) keep the turn testable rather than a soup of flags:
- `normal_choice`: active player may draw, take the discard, or (if unlocked) call Dutch.
- `draw_reveal`: only the drawer sees the drawn face until `reserved.until = now + DrawPreviewSeconds`; then they **swap** or **discard straight away**. Face hides on expiry even if undecided.
- `swap_select`: choose exactly one unlocked own slot to replace; persist once.
- `power_select`: a power card was discarded straight away; run the Jack/Queen/King interaction (§6) within the turn.
- `discard_resolving`: a card landed face up; if cutting is unlocked and not in `dutch_final`, open/refresh `cut_window`.
- `dutch_final`: walk `final_turn_order`, one swap each; no cut, no second Dutch call.
- `round_results` / `match_results`: immutable until an authorized `next_round` / `rematch`.

**Timer model (lazy, server-owned).** Keep the existing architecture: no background worker. `tick(state, now)` resolves every deadline on any read or action, and connected consumers poll (~250 ms) to drive it. `tick` must handle, in order: expiring initial/draw/power reveals; `choose_reveal` and `initial_peek` setup timeouts; and the **30 s turn deadline** (§5). A page refresh, extra tab, or edited client must never lengthen a reveal or a turn — expire at the server before building any snapshot.

## 5. Turn and timer model (new)

Each turn gets `turn_deadline = now + TurnSeconds` (30 s) set when the turn becomes active. `tick` enforces it:
- **Timeout before the player draws/takes** → skip the turn. It still sets `first_turn_done[seat]` (counts for the unlock). Advance to the next seat (or next `final_turn_order` entry).
- **Timeout after a draw** (a `reserved` card is held) → auto-discard the drawn card face up. A power card auto-discarded this way grants **no** power. Then advance the turn.
- The 3 s draw preview and any power selection live **inside** the 30 s; an unfinished power is lost at the deadline.

Because turns self-advance on timeout, the table never blocks on a slow or disconnected player (§11). `turn_deadline` is public so every client can render the countdown.

## 6. Power cards — Jack, Queen, King

Trigger for all three: the active player **draws from the draw pile and discards it straight away** (the `discard_drawn` action), and the discarded card is a J/Q/K. Using the power is optional; it never changes turn order, is not a swap or a cut, and must complete before the turn deadline. A power card that is swapped out of the grid, taken from the discard pile, cut, or auto-discarded on timeout grants **no** power.

- **Jack — peek.** Choose one of your own cards; see its face privately for `JackPeekSeconds` (1 s), then it hides. Never reveals another player's card.
- **Queen — blind swap.** Choose one of your own cards and one card in any opponent's hand; the two cards exchange slots, **face down, neither face revealed**. Public projection shows *which two slots* exchanged, never the faces. Locked cards (King lock or a Dutch caller's hand) are not selectable on either side.
- **King — lock / unlock.** Either lock one card (turn it **face up**, publicly visible, and set `locked`) or unlock one currently locked card (clears `locked`; the card turns **face down** again — `UnlockedCardFaceDown` default). Target may be **any** player's hand including your own (`KingTarget` default). A locked card cannot be swapped (drawn/discard/Queen), discarded or cut while locked. A card in a Dutch caller's hand cannot be locked or unlocked.

Represent an in-progress power as `state['power']` with a `kind`, the owner identity, a selection step, and a time box where applicable (Jack's 1 s reveal). Only the owner's projection exposes a Jack face; Queen/King results are public at the slot level.

## 7. Cutting (event-based window)

When any card lands face up (normal swap discard, discard-drawn, or a successful cut), and cutting is unlocked (every seat has finished its first turn) and not in `dutch_final`, open `cut_window = {event_id, rank}` for the current top discard. There is **no fixed timer**: the window stays open until the next player plays (draw / take / call Dutch), at which point it clears. The first valid cut command, by serialized server arrival, wins.

- Own, **unlocked** cards only; one card per cut (`MultiCardCut` default false). Trying to cut a locked card is rejected with no penalty.
- **Success:** the card moves to the discard pile, the hand shrinks permanently, the **cutter takes the next turn**, and (default `CutOnCutCard`) the cut card opens a fresh `cut_window`. If the hand is now empty, finish the round immediately (cutter scores 0) and cancel pending timers/powers.
- **Failed cut (wrong rank):** the card returns to its slot face down; add **one** face-down penalty card from the draw pile (never shown). The card is revealed publicly for `FailedCutRevealSeconds` (2 s) via `cut_reveal`, then hidden. Default `FailedCutterTakesNextTurn` false → turn order continues normally.
- A cut against a stale `event_id`, or after Dutch, or on an empty/zero draw pile for the penalty, follows the exhaustion fallback (§ rules 10): no invented card.

## 8. Redacted projection and anti-cheat

`dutch_engine.public(state, viewer, now)` is an explicit allowlist serializer (build the dict from scratch — never `dict(state)` then delete). Reconnect/resync use the same function so expired reveals are already gone. A separate, stricter spectator projection (viewer = None) exposes strictly less.

**Public to everyone:** `game_type, status, phase, round, max_rounds, player_limit, host`, sanitized players (name/avatar/connected/ready), hand **counts**, top discard face, draw-pile **count**, `turn`, `turn_id`, `turn_deadline`, `chooser`, `reveal_count`, whether cut/Dutch is unlocked, `dutch_caller`, `final_turn_order`/progress, scores, and — new to this ruleset — every **locked** card's face, the **replaced slot** of a swap, the two slots of a Queen swap (faces hidden), and the current **cut** card including a failed cut's face while `cut_reveal` is live.

**Private to the viewer only:** own seat, own slot handles (not faces), which own slots are selectable, the `reserved` drawn face only while `now < reserved.until`, a Jack-peeked own face only while its 1 s window is live, and own initial-peek faces only during the authorized 3 s.

**Round-end disclosure:** all hands and the score breakdown, only once `status` is `round_results`/`match_results`.

Never send `hands`, `cards`, `draw_pile`, the full `discard_pile`, `commands`, identities or session ids to any client. Public card ids are re-randomized per round; only a player's own slot handles are stable enough to interact with, and they must not leak deck order. HTTP fallback stays CSRF-protected; rate-limit room creation, joins, cut spam and socket actions.

## 9. Backend action protocol

All commands verify: correct `game_type`/room, authenticated seated identity, phase and turn/seat ownership, requested slot/card ownership, server-owned discard rank (never trust a submitted rank), a client command UUID for idempotency, and a monotonic `turn_id`/`revision` to drop stale turn-scoped actions. Every mutation runs inside `transaction.atomic()` + `select_for_update()` (the DB lock is the real cross-worker guard; the thread mutex is in-process only), consistent with `game/service.py`.

Actions (WebSocket `dutch.<action>` and HTTP `/dutch/api/<action>/`):

| Action | Fields | Meaning |
|---|---|---|
| `ready` | command | Toggle lobby readiness |
| `start` | command | Host starts with all seats filled, connected, ready |
| `choose_reveal` | count, command | Chooser picks the reveal count 0–4 |
| `initial_peek` | slots[], command | Pick exactly `reveal_count` own cards for the 3 s peek |
| `draw` | command, turn_id | Reserve the top draw card; private 3 s preview |
| `swap_drawn` | slot, command, turn_id | Swap the reserved card into an unlocked own slot |
| `discard_drawn` | command, turn_id | Discard the reserved card straight away (may trigger a power) |
| `take_discard` | slot, command, turn_id | Take the top discard and swap into an unlocked own slot |
| `jack_peek` | slot, command | Jack power: peek one own card (1 s) |
| `queen_swap` | own_slot, target_seat, target_slot, command | Queen power: blind cross-hand swap |
| `king_lock` | target_seat, target_slot, mode(lock/unlock), command | King power: lock or unlock a card |
| `power_skip` | command | Decline the pending power |
| `cut` | slot, event_id, command | Cut one own card matching the current discard |
| `call` | command, turn_id | Call Dutch; build `final_turn_order` |
| `next_round` | command | Host advances after results (until round 10) |
| `rematch` | command | Reset scores, new 10-round match |
| `leave` / `delete` | command | Lobby leave / host delete |
| `resync` / `tick` | — | Fresh redacted snapshot / drive timers |

Presence actions (`connect`/`heartbeat`/`disconnect`) keep the lease model from the current build. Server notifications (public, never carrying hidden faces): `round.started, reveal.chosen, peek.available, draw.preview, card.discarded, power.used, cut.opened, cut.accepted, cut.penalty, dutch.called, final.turn, round.finished, match.finished, game.error`. Reuse existing room-chat events.

## 10. Scoring

Card values A=1 … K=13 (`CardValues`, confirmed). Locked cards count normally. Round-end cases:
- **Empty-hand cut:** cutter 0; everyone else their hand total.
- **Dutch, caller strictly lowest:** caller 0; everyone else their total.
- **Dutch, anyone ties or beats the caller:** caller **2 × their own total**; everyone else their total. (`DutchTieCountsAsWin` false — a tie **fails**.)

Worked checks (from the rules): caller 9 vs 7/12/16 → caller **18**; caller 7 with another 7 → tie fails, caller **14**; caller 5 vs 7/12/16 → caller **0**. After exactly 10 rounds the lowest cumulative total wins; equal lows are joint winners.

## 11. Disconnects (no pause)

`PauseOnDisconnect` default is **false**: do not pause. A disconnected seat keeps its place and rides the normal 30 s turn timer — its turns simply time out and skip (§5). On reconnect the player gets the full state back: hand positions, locked cards, turn order, remaining `final_turn_order`, and any still-valid private peek (never a restarted one).

Keep the lease-based presence from the current build for *rendering* connection dots, but it no longer gates play. **All-idle safeguard (confirmed, kept):** if **no** seated player is connected for one full turn cycle, abandon the round (`status='abandoned'`) without scoring, rather than skipping turns forever on a dead table. This is the one design decision the rules don't cover; it is configurable and defaults to on.

## 12. Configuration object

Rebuild `game/dutch_rules.py` as one validated config dict mirroring the `RULES_DUTCH.md` Configuration table, overridable via `settings.DUTCH_RULES`, frozen per room at creation (`state['rules']`). Validate ranges and types and reject unknown keys, as the current module does. There are **no** hard-coded, non-configurable invariants in the new ruleset (the old "2 s draw / no final cuts / 10 rounds are not switches" wording goes away) — but confirmed values should not be changed casually.

Keys (confirmed): `Players 2–6, UseJokers false, CardValues, RevealCountRange 0–4 rotating-right, StartingPeekSeconds 3, DrawPreviewSeconds 3, TurnSeconds 30, AllowDiscardDrawnCard true, PowerCards (J peek / Q blind-swap / K lock-unlock, drawn-and-discarded-straight-away), JackPeekSeconds 1, CutUnlock after-first-turn/first-discard-never, CutOpponentCards false, CutWindow until-next-play, CutterTakesNextTurn true, FailedCutPenaltyCards 1, CutsArePublic true, EmptyHandEndsRound true, CutDuringDutchFinal false, DutchFinalTurn one-each/caller-locked, DutchTieCountsAsWin false, FailedDutchMultiplier 2, Rounds 10, ReconnectFullResume true, ReplacedSlotIsPublic true`.

Keys (**[DEFAULT — CONFIRM]**): `FirstPlayer=chooser, SetupChoiceSeconds=15, TimeoutBeforeDraw=skip, TimeoutAfterDraw=auto-discard-no-power, KingTarget=any-player, UnlockedCardFaceDown=true, CutLockedCard=blocked-no-penalty, MultiCardCut=false, CutOnCutCard=true, FailedCutterTakesNextTurn=false, FailedCutRevealSeconds=2, MatchTie=joint-winners, EmptyDrawPile=reshuffle-except-top, PauseOnDisconnect=false`, plus the all-idle safeguard from §11.

## 13. Front-end / table UI and animation plan

`RULES_DUTCH.md` §13 is the UI spec; implement it in `templates/dutch/index.html` + `dutch.js` + `dutch.css`. Reuse brand tokens and accessible controls; keep the own-hand anchored at the bottom; 320 px+, oversized tap targets, overlays for cut/scores/rules, no page-width overflow, tap-pile-then-slot (never drag-only), reduced-motion fallbacks, and never show an opponent face during a flip or reconnect. **Opponent card sizing:** render other players' cards slightly larger than the current build so seats stay easy to track across a 2–6 player table (still smaller than the own-hand anchor, but with a bump in card and slot-grid size and clearer per-seat counts). New screens/affordances versus the current UI:
- **Chooser prompt:** when you are the chooser, pick 0–4 with a 15 s countdown; others see "waiting for the chooser".
- **Starting peek:** handle 0 (skip) through 4 (whole hand), 15 s auto-pick.
- **30 s turn timer:** every seat shows the active player's glow + countdown; the active player gets the stronger "Your turn" treatment and a larger countdown.
- **Draw flow:** 3 s private reveal, then **swap into a slot** or a **"Discard instead"** button; locked slots greyed and unselectable.
- **Powers:** Jack (own-slot peek, 1 s), Queen (pick own slot + opponent slot; both slide face down), King (lock → face-up with lock icon / unlock → face down). Public views show the slots involved, not hidden faces.
- **Cutting:** single-card select, available until the turn advances (no countdown ring); success flashes + jumps the turn to the cutter; failed cut shows the card publicly ~2 s with a negative effect, then a face-down penalty slides in.
- **Round/results:** reveal all hands, hand totals and round scores (highlight 0 and 2×), cumulative scores, then final scoreboard + winner(s) + Play again.
- Remove all "paused / waiting for players" banners — the no-pause model means turns simply time out.

## 14. Edge cases that must be resolved

1. Reveal count 0 → skip the peek phase entirely; 4 → every own card peekable.
2. Chooser / peek timeout → server auto-pick (random count; nearest cards bottom-row-first) without revealing anything publicly.
3. Turn timeout before vs after draw → skip vs auto-discard-no-power; always advances exactly once; `first_turn_done` set on a skip.
4. Power only on draw-then-discard-straight-away; swapped/taken/cut/auto-discarded power cards grant nothing.
5. Queen/King may not touch a locked card or any card in a Dutch caller's locked hand; King can't lock/unlock a caller's hand.
6. Two players cut the same discard → one accepted by serialized arrival; the other gets a stale-`event_id` rejection with no penalty.
7. Cut window closes exactly when the next player plays; a late cut against the previous `event_id` is rejected.
8. Failed cut → one unseen penalty, 2 s public reveal, turn order unchanged (default); exhausted draw pile → no penalty card minted.
9. Empty-hand cut outranks any pending power/Dutch; round ends immediately with no final turns.
10. Dutch tie fails (caller 2×); exactly N−1 final turns, swap-only, no cut, no second call; caller hand fully locked.
11. Disconnect mid-turn → the 30 s timer still fires and skips; reconnect restores state and any still-valid peek, never a restarted one. All-idle → abandon per §11.
12. Card conservation: never create or lose a card across swap / discard-drawn / Queen / cut / penalty / reshuffle.
13. 2/3/5/6 players: chooser rotation, turn order, final-turn order, counts, UI and scoring with no hard-coded 4-seat assumptions.
14. Round 10 → match_results exactly once; no 11th round; no early stop on score.
15. Private-data leak check across every role: host, player, spectator, guest, non-member, disconnected tab, reconnecting tab.
16. Room collision: a 10 code on `/dutch/room/` (and a Dutch code on `/room/`) must not load; middleware + consumer guards hold.

## 15. Test plan

Engine unit tests (`game/test_dutch_engine.py`): 52 unique cards and correct deals for 2–6; conservation across every mutation; rotating chooser + 0–4 reveal + chooser-starts; authorized/time-boxed initial peeks incl. count 0; 30 s turn skip and post-draw auto-discard; discard-drawn triggers; each power (Jack peek, Queen blind swap, King lock/unlock) incl. locked-card and caller-locked rejections; cut unlock, single cut, cutter-takes-turn, failed-cut penalty + turn-unchanged + 2 s reveal, empty-hand cut 0; Dutch final order (N−1, once), swap-only, tie-fails 2×, strict-lowest 0; exactly 10 rounds, joint-winner ties; exhausted-deck reshuffle and no-mint fallback.

Service / WS / concurrency tests: guest join by code but no acting for others' seats; host-only start/next/rematch/delete; transactional concurrent cut vs play never corrupts state; replayed command UUID never double-draws/cuts/penalizes/scores; A's snapshot never contains B's hidden faces/deck order/private reveal (incl. the new public locked/cut/slot fields verified to leak nothing hidden); spectator allowlist; reconnect/resync hides expired peeks; **all existing 10 tests still pass**; row-lock race tests on PostgreSQL (skip on SQLite). Browser scripts under `tests/` updated for the new flow.

Manual end-to-end: 2–6 profiles; chooser pick incl. 0 and 4; peek timers; both take sources; discard-drawn with each power; single cut, failed cut, empty-hand cut; one successful and one failed Dutch (incl. a tie); verify N−1 final swaps with no cut; 10-round scoreboard; a disconnect that skips on the timer and a clean reconnect.

## 16. Build sequence

1. Baseline: `python manage.py test` green; confirm the 10 suite is the protected reference.
2. `dutch_rules.py`: new config object + validation. Tests first.
3. `dutch_engine.py`: state shape, chooser/reveal, peeks, turn timer, swap/discard-drawn, powers, cutting, Dutch final, scoring. Engine unit tests first, driven by explicit `now`/RNG.
4. `dutch_service.py`: lobby/host/lifecycle, atomic mutate dispatch for the new actions, presence (no-pause) + all-idle safeguard, idempotency, per-seat projection.
5. `dutch_consumer.py` + `dutch_views.py`: action allowlists, public snapshots, lazy timer ticks, stale-command protection, isolation guards intact.
6. Front-end: `index.html` + `dutch.js` + `dutch.css` per §13.
7. Concurrency/security validation; update browser scripts.
8. Full suite green; manual 2- and 6-player matches. No production deploy.

Dev commands (Windows): `python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt; python manage.py migrate; python manage.py test; python manage.py runserver 127.0.0.1:8000`.

## 17. Open decisions

Everything marked **[DEFAULT — CONFIRM]** in §12 follows `RULES_DUTCH.md` and stays configurable. The only decision the rules don't address, the **all-idle safeguard** in §11 (abandon a round when no seat is connected for a full turn cycle), is **confirmed kept**, default on. Flag any of these for owner confirmation rather than hard-coding them as rules.
