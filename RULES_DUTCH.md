# Dutch — consolidated rules

Dutch is a memory card game. The aim is to finish each round with the **lowest total card value**
in front of you. You never see most of your own cards, so you have to remember them.

This file is the single source of truth for the Dutch engine and table UI. It replaces the earlier
`RULES_DUTCH.md` and the rules sections of `DUTCH_IMPLEMENTATION.md`. Rules marked
**[DEFAULT — CONFIRM]** fill gaps the owner has not decided yet; keep each one configurable
(see *Configuration* at the end) and do not present it as a confirmed rule.

---

## 1. Players and deck

- **2–6 players**, individual play (no teams).
- One standard **52-card deck**, no jokers. Shuffled server-side with a cryptographically secure RNG
  at the start of every round.

## 2. Card values

| Card | Points |
|---|---|
| Ace | 1 |
| 2–10 | Face value |
| Jack | 11 |
| Queen | 12 |
| King (any suit) | 13 |

## 3. Setup (every round)

1. Deal each player **4 cards face down** in a 2×2 grid. Slot positions stay fixed for the round
   unless cards are removed by cutting, added as penalties, or **a drawn card enters at the leftmost
   slot** (see §4).
2. Turn the next card face up to start the **discard pile**. The rest form the face-down **draw pile**.
3. **Reveal count (rotating chooser).**
   - One player, the **chooser**, picks a number from **0 to 4**.
   - The chooser role rotates **one seat to the right each round**: round 1 = the first seat,
     round 2 = the seat to its right, and so on.
   - `0` means a blind round; `4` means everyone sees their whole hand.
4. **Starting peek.** Every player **chooses which of their own cards** to look at (exactly the
   chosen count). Selecting happens blind within a **10-second** window; then **everyone's chosen
   cards are revealed at the same time for 3 seconds** (each player sees only their own), and play
   starts. If a player chooses nothing in time, the server picks their nearest cards (bottom row
   first). The chooser likewise has **10 seconds** to pick the number, and picking ends that timer
   at once.
5. **Turn order** goes **to the right** (the same direction as the chooser rotation).
   **[DEFAULT — CONFIRM]** The chooser takes the first turn of the round.

## 4. Your turn

Each turn has a **30-second timer**. On your turn you do exactly one of:

1. **Draw from the draw pile.** The drawn card **enters your hand at the leftmost slot** and is shown
   to you **privately for 3 seconds** (it hides after 3 seconds even if you haven't decided). Then
   choose which card to **discard**:
   - **discard the drawn card itself** (face up). If it is a **Jack, Queen or King**, you may use its
     power (section 5); or
   - **discard one of your other cards** instead, keeping the drawn card at the leftmost slot.
2. **Take the top card of the discard pile.** You must **swap** it with one of your cards; the taken
   card lands **in that card's slot** and the replaced card goes face up onto the discard pile.
3. **Call "Dutch"** (section 7), only at the start of your turn and only once cutting/Dutch are
   unlocked.

A **locked** card (section 5, King) can never be chosen as the card to replace.

### Turn timer

- **[DEFAULT — CONFIRM]** If the timer runs out **before you draw or take**, your turn is skipped.
  It still counts as your turn for the first-turn unlock.
- **[DEFAULT — CONFIRM]** If the timer runs out **after you have drawn** but before you decide, the
  drawn card is discarded automatically, and a power card discarded this way has **no power**.
- **[DEFAULT — CONFIRM]** The 3-second draw preview and any power fall within the 30 seconds; they do
  not extend the timer. A power not finished in time is lost.
- **[DEFAULT — CONFIRM]** Choosing the reveal count and the starting peek have their own
  **10-second** limits. If the chooser times out, the server picks the number at random; if a player
  times out on the starting peek, the server picks their nearest cards (bottom row first).

## 5. Power cards: Jack, Queen and King

- Only the **Jack**, **Queen** and **King** have powers. No other card has one.
- **Trigger (all three):** a power card that you **draw from the draw pile and discard straight
  away**. A power card swapped out of your grid, taken from the discard pile, or cut has
  **no power**.
- Using a power is optional. Powers don't change turn order and don't count as a swap or a cut.

### Jack: peek

- Choose **one of your own cards** and look at it **privately for 1 second**. It then turns face
  down again. You never see another player's card through this power.

### Queen: blind swap

- Swap **one card from your hand** (your choice) with **one card from any opponent's hand**.
- **Neither player sees** either card. Each card takes the other's slot, face down.
- A **locked** card (King lock or a Dutch caller's hand) cannot be chosen, on either side.

### King: lock / unlock

- **Lock:** turn one card **face up** and lock it. Everyone can see it.
- A locked card **cannot be swapped** (with a drawn card, with the discard pile, or by a Queen)
  and **cannot be discarded or cut**. It still counts toward its owner's hand total.
- **Unlock:** a King's power can instead be used to **unlock** a locked card. Only after it is
  unlocked can it be swapped, discarded or cut again.
- **[DEFAULT — CONFIRM]** A King can lock or unlock a card in **any player's** hand, including
  your own.
- **[DEFAULT — CONFIRM]** An unlocked card turns **face down** again.
- **[DEFAULT — CONFIRM]** A card in a Dutch caller's hand cannot be locked or unlocked; their whole
  hand is already locked.

## 6. Cutting

When a card lands face up on the discard pile, players may throw a card of the **same rank**
(suit doesn't matter) from **their own hand** onto it. This is a **cut**.

- **Unlock:** cutting is not allowed until **every seated player has had their first turn** of the
  round. The first face-up discard dealt at setup can never be cut.
- **Own cards only:** you can only cut cards from your own hand. You cannot cut an opponent's card.
- **Locked cards** cannot be cut. **[DEFAULT — CONFIRM]** Trying to cut a locked card is blocked by
  the UI and rejected by the server (no penalty).
- **Window:** a cut must happen **before the next player plays** (draws, takes the discard, or calls
  Dutch). The server processes actions in order; the first valid cut is the one that counts.
- **Successful cut:** your card goes onto the discard pile and your hand shrinks permanently.
  **The cutter takes the next turn**, and play continues to the right from them.
- **Failed cut (wrong rank):** the card goes back to its slot face down and you get **one penalty
  card** from the draw pile, face down. You never see the penalty card.
- **Cutting your last card:** the round **ends immediately**. No one gets another turn. The cutter
  scores **0**; everyone else scores their remaining hand total.
- **After Dutch is called:** cutting is disabled for the rest of the round.
- **Public:** every player sees the card that was cut and whether the cut succeeded or failed
  (section 13).
- **[DEFAULT — CONFIRM]** One card per cut (no multi-card cuts).
- **[DEFAULT — CONFIRM]** A cut card is itself a new discard, so it opens a new cut opportunity
  until the cutter plays.
- **[DEFAULT — CONFIRM]** After a failed cut, turn order continues normally; the failed cutter does
  **not** take the next turn.

## 7. Calling "Dutch"

- **When:** at the **start of your own turn**, instead of drawing, once every seated player has had
  their first turn of the round. It cannot be cancelled and can only be called once per round.
- **Final turns:** every **other** player gets **exactly one more normal turn**, in turn order
  starting from the player to the caller's right. The caller gets no further turn.
- The caller's cards are **locked**; nothing may change them for the rest of the round
  (including Queen swaps and King locks/unlocks).
- No cutting during the final turns.
- After the last final turn, everyone's cards are revealed and the round is scored.

## 8. Scoring

At the end of each round, every player adds their round score to their running total.

| How the round ended | Round score |
|---|---|
| Someone cut their last card | Cutter **0**; everyone else their hand total |
| Dutch called, caller has the **strictly lowest** total | Caller **0**; everyone else their hand total |
| Dutch called, anyone **ties or beats** the caller | Caller **2 × their hand total**; everyone else their hand total |

Locked cards count toward their owner's total like any other card.

**Examples**

- Failed Dutch: caller has 9, others have 7, 12 and 16 → caller scores **18**, others 7 / 12 / 16.
- Tie: caller has 7, another player has 7 → the call **fails**, caller scores **14**.
- Successful Dutch: caller has 5, others 7, 12 and 16 → caller scores **0**, others 7 / 12 / 16.

## 9. Ending the match

- A match is **exactly 10 rounds**. There is no early stop based on score.
- After round 10, the **lowest cumulative score** wins.
- **[DEFAULT — CONFIRM]** Equal lowest totals are **joint winners**; no tiebreaker.

## 10. Running out of cards

- **[DEFAULT — CONFIRM]** When the draw pile is empty, keep the top discard face up, shuffle the rest of
  the discard pile into a new draw pile and continue.
- **[DEFAULT — CONFIRM]** If no cards are left to reshuffle, drawing is blocked (taking the discard and
  calling Dutch still work), and a failed cut gives no penalty card. Cards are never created or lost.

## 11. Disconnects

- A disconnected player keeps their seat. When they reconnect, they get the **full state back**:
  their hand positions, locked cards, the turn order, the remaining final-turn order after a Dutch
  call, and any private peek that is still within its time limit (never a restarted one).
- **[DEFAULT — CONFIRM]** The game does not pause. A disconnected player's turns run on the normal
  30-second timer and are skipped if they don't act.

## 12. Hidden information

The server owns the deck and every hidden card. A client only receives the face of a card it is
currently allowed to see.

**Private (only that player):**

- the cards it chose during the starting peek, for 3 seconds;
- a card it drew from the draw pile, for 3 seconds;
- its own card chosen with a Jack power, for 1 second.

**Public (everyone):**

- the top discard;
- every **locked** card, for as long as it stays locked;
- every **cut** card, including a failed cut's card while it is shown (section 13);
- **which slot** a player replaced on a swap, and which two slots a Queen swapped (never the
  card faces involved, except the card that lands face up on the discard pile);
- all hands at the end-of-round reveal.

Everything else is sent face down. Public state also includes hand **counts**, the draw pile count,
whose turn it is, the timer deadline, who called Dutch, and scores. Expired peeks must be hidden by
the server; refreshing or reconnecting must not extend them.

## 13. Table display and animations

Animations are for clarity only. They never extend a timer, delay the server, or reveal a card
face that the viewer isn't allowed to see. Respect the device's reduced-motion setting by
replacing movement with simple fades and highlights.

### Active player

- **Everyone** sees which player is active: their seat is highlighted (glow or ring) and shows
  the turn timer counting down.
- **The active player's own view** is much stronger: a clear "Your turn" banner, their hand and the
  two piles highlighted as tappable, and a larger countdown.
- During Dutch final turns, the caller is marked as "Dutch" and remaining final turns are shown.

### Choosing which card to replace

- After drawing, the drawn card slides from the deck into the **leftmost slot** of the active
  player's hand (face up to them for 3s, face down to everyone else), and they get a "choose a card
  to discard" prompt: tapping the drawn card discards it, tapping another keeps the draw. Locked
  cards are **greyed out** and not selectable.
- **Other players see the drawn card enter at the leftmost slot and which card then flies to the
  discard**, so the swap is legible to everyone.
- Taking from the discard pile animates the face-up card from the pile into the chosen slot (the
  replaced card flies to the discard), then it turns face down.
- **Cutting is a double-tap / double-click** on one of your own cards while a cut window is open
  (there is no separate cut button).

### Cuts

- **Successful cut:** the cutter's card flips face up and flies onto the discard pile, with a
  positive effect (e.g. green flash) and a short "Cut!" label on the cutter's seat. Everyone sees it.
  The turn indicator then jumps to the cutter.
- **Failed cut:** the card flips face up in front of the cutter so everyone can see it, shakes with
  a negative effect (e.g. red flash, "Wrong cut" label), then flips face down back into its slot.
  A penalty card then slides face down from the draw pile into the cutter's hand.
- **[DEFAULT — CONFIRM]** A failed cut's card stays visible for **2 seconds** before turning face down.
- **Cutting the last card:** after the success animation, go straight to the round-win
  animation and the round results.

### Powers

- **Jack:** everyone sees "Jack: peek" on the active player's seat, and which of their slots was
  chosen. Only the active player sees the card face.
- **Queen:** both swapped slots are highlighted and the two cards slide past each other, face down.
- **King:** a locked card flips face up and shows a lock icon; unlocking removes the icon and the
  card flips face down.

### Round end

- Reveal all hands, show each hand's total and round score (highlight 0 for a winning Dutch or
  empty-hand cut, and 2× for a failed Dutch), then cumulative scores.
- After round 10, show the final scoreboard, the winner(s) and a "Play again" option.

---

## Configuration

All values below live in one config object. Confirmed rules are listed for reference; they should
not be changed casually.

| Setting | Value | Status |
|---|---|---|
| `Players` | 2–6 | Confirmed |
| `UseJokers` | false | Confirmed |
| `CardValues` | A=1, 2–10 face, J=11, Q=12, K=13 | Confirmed |
| `RevealCountRange` | 0–4, rotating chooser, rotates right | Confirmed |
| `StartingPeekSeconds` | 3 | Confirmed |
| `DrawPreviewSeconds` | 3 | Confirmed |
| `TurnSeconds` | 30 | Confirmed |
| `AllowDiscardDrawnCard` | true | Confirmed |
| `PowerCards` | Jack peek, Queen blind swap, King lock/unlock; drawn and discarded straight away | Confirmed |
| `JackPeekSeconds` | 1 | Confirmed |
| `CutUnlock` | After every player's first turn; first discard never cuttable | Confirmed |
| `CutOpponentCards` | false | Confirmed |
| `CutWindow` | Until the next player plays | Confirmed |
| `CutterTakesNextTurn` | true | Confirmed |
| `FailedCutPenaltyCards` | 1 | Confirmed |
| `CutsArePublic` | true (card and result shown to all) | Confirmed |
| `EmptyHandEndsRound` | true, cutter scores 0 | Confirmed |
| `CutDuringDutchFinal` | false | Confirmed |
| `DutchFinalTurn` | One normal turn each, caller's cards locked | Confirmed |
| `DutchTieCountsAsWin` | false | Confirmed |
| `FailedDutchMultiplier` | 2 | Confirmed |
| `Rounds` | 10, no score cut-off | Confirmed |
| `ReconnectFullResume` | true | Confirmed |
| `ReplacedSlotIsPublic` | true | Confirmed |
| `FirstPlayer` | The chooser | Default — confirm |
| `SetupChoiceSeconds` | 10 (reveal count pick, and the card-select window) | Default — confirm |
| `DrawEntersLeftmost` | true (drawn card enters the leftmost slot; then discard any one card) | Confirmed |
| `CutInteraction` | Double-tap a card (no cut button) | Confirmed |
| `TimeoutBeforeDraw` | Skip turn | Default — confirm |
| `TimeoutAfterDraw` | Auto-discard, no power | Default — confirm |
| `KingTarget` | Any player's card | Default — confirm |
| `UnlockedCardFaceDown` | true | Default — confirm |
| `CutLockedCard` | Blocked, no penalty | Default — confirm |
| `MultiCardCut` | false | Default — confirm |
| `CutOnCutCard` | true | Default — confirm |
| `FailedCutterTakesNextTurn` | false | Default — confirm |
| `FailedCutRevealSeconds` | 2 | Default — confirm |
| `MatchTie` | Joint winners | Default — confirm |
| `EmptyDrawPile` | Reshuffle discards except top | Default — confirm |
| `PauseOnDisconnect` | false | Default — confirm |
