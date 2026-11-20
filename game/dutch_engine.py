"""Standalone Dutch state machine. No database, no 10 engine; explicit clock/RNG.

`RULES_DUTCH.md` is the rules source of truth; this implements it. Only public()
may cross the network boundary. Slot handles are per-round random tokens that are
independent of card identities and survive swaps; a discarded/cut face never
carries a hidden id. Timers are server-owned and resolved lazily in tick().
"""
import copy
import secrets
from .dutch_rules import rules, RANKS

SUITS = 'CDHS'
ACTIVE = {'choose_reveal', 'initial_peek', 'playing', 'dutch_final'}
RESULTS = {'round_results', 'match_results'}
POWER_RANKS = {'J': 'jack', 'Q': 'queen', 'K': 'king'}


def require(condition, message):
    if not condition: raise ValueError(message)


def token(rng=None):
    return f'{(rng or secrets.SystemRandom()).getrandbits(128):032x}'


def event(s, kind, seat=None, **fields):
    s['event_counter'] += 1
    s['event'] = {'id': s['event_counter'], 'kind': kind, 'seat': seat, **fields}


def new_state(n, identity, name, now, overrides=None):
    require(type(n) is int and 2 <= n <= 6, 'Choose 2–6 seats.')
    return {
        'game_type': 'dutch', 'schema_version': 2, 'rules': rules(overrides),
        'status': 'lobby', 'phase': 'lobby', 'host': 0, 'player_limit': n,
        'players': [{'id': identity, 'name': name, 'ready': False, 'connected': False, 'connections': {}}] + [None] * (n - 1),
        'round': 0, 'max_rounds': 10, 'scores': [0] * n, 'round_history': [], 'round_result': None, 'winner_seats': [],
        'chooser': None, 'reveal_count': None, 'starter': None, 'turn': None, 'turn_id': 0, 'turn_deadline': None,
        'setup_deadline': None, 'first_turn_done': [False] * n,
        'hands': [[] for _ in range(n)], 'cards': {}, 'draw_pile': [], 'discard_pile': [],
        'initial_peeks': {}, 'peek_reveal_until': None,
        'reserved': None, 'power': None, 'cut_window': None, 'cut_reveal': None,
        'dutch_caller': None, 'final_turn_order': [], 'final_turn_index': 0,
        'event_counter': 0, 'event': None, 'commands': [],
        'created_at': now, 'revision': 0, 'invitation_closed': False,
    }


# --- round lifecycle ---------------------------------------------------------

def chooser_for(s):
    return ((s['round'] - 1) * s['rules']['direction']) % s['player_limit']


def next_seat(s, seat):
    return (seat + s['rules']['direction']) % s['player_limit']


def start(s, seat, now, rng=None):
    require(s['status'] == 'lobby' and seat == s['host'], 'Only the host can start a lobby.')
    require(all(p and p['ready'] and p['connected'] for p in s['players']), 'Fill every seat; everyone must be connected and ready.')
    s.update(scores=[0] * s['player_limit'], round_history=[], round=0, winner_seats=[], invitation_closed=True)
    next_round(s, now, rng)


def next_round(s, now, rng=None):
    require(s['round'] < s['rules']['rounds'] and (s['round'] == 0 or s['status'] == 'round_results'), 'There is no next round.')
    rng = rng or secrets.SystemRandom()
    n = s['player_limit']; s['round'] += 1
    s['cards'] = {token(rng): {'rank': r, 'suit': su} for su in SUITS for r in RANKS}
    deck = list(s['cards']); rng.shuffle(deck)
    s['hands'] = [[{'slot': token(rng), 'card': deck.pop(), 'locked': False} for _ in range(4)] for _ in range(n)]
    s['discard_pile'] = [deck.pop()]; s['draw_pile'] = deck
    s['chooser'] = s['starter'] = chooser_for(s)
    s.update(status='choose_reveal', phase='choose_reveal', reveal_count=None,
             setup_deadline=now + s['rules']['setup_choice_seconds'], turn=None, turn_deadline=None,
             first_turn_done=[False] * n, initial_peeks={}, peek_reveal_until=None,
             reserved=None, power=None, cut_window=None, cut_reveal=None,
             dutch_caller=None, final_turn_order=[], final_turn_index=0, round_result=None)
    s['turn_id'] += 1; event(s, 'round.started')


def set_reveal_count(s, count, now):
    r = s['rules']
    require(type(count) is int and r['reveal_min'] <= count <= r['reveal_max'], 'Pick a reveal count in range.')
    # The chooser's pick ends the choose timer at once and opens the shared select window.
    s['reveal_count'] = count
    s.update(status='initial_peek', phase='select', setup_deadline=now + r['setup_choice_seconds'],
             initial_peeks={}, peek_reveal_until=None)
    if count == 0: begin_play(s, now)


def all_full(s):
    return all(len(s['initial_peeks'].get(str(i), {}).get('slots', [])) == s['reveal_count'] for i in range(s['player_limit']))


def fill_reveal(s, now):
    # Fill each player's picks up to reveal_count (nearest, bottom row first), then reveal all at once.
    for i in range(s['player_limit']):
        chosen = s['initial_peeks'].get(str(i), {}).get('slots', [])
        handles = {e['slot'] for e in chosen}
        for entry in reversed(s['hands'][i]):
            if len(chosen) >= s['reveal_count']: break
            if entry['slot'] not in handles:
                chosen.append(copy.deepcopy(entry)); handles.add(entry['slot'])
        s['initial_peeks'][str(i)] = {'owner': s['players'][i]['id'], 'slots': chosen[:s['reveal_count']]}
    start_reveal(s, now)


def start_reveal(s, now):
    # Everyone's peek is revealed simultaneously; each viewer only ever sees their own.
    until = now + s['rules']['starting_peek_seconds']
    s['phase'] = 'reveal'; s['peek_reveal_until'] = until; s['setup_deadline'] = None
    for peek in s['initial_peeks'].values():
        peek['until'] = until


def begin_play(s, now):
    s.update(status='playing', setup_deadline=None, peek_reveal_until=None, initial_peeks={})
    begin_turn(s, s['starter'], now)


def begin_turn(s, seat, now):
    s.update(turn=seat, phase='normal_choice', reserved=None, power=None,
             turn_deadline=now + s['rules']['turn_seconds'])
    s['turn_id'] += 1


def advance(s, seat, now):
    if s['status'] == 'dutch_final':
        s['final_turn_index'] += 1
        if s['final_turn_index'] >= len(s['final_turn_order']):
            finish(s, 'dutch', s['dutch_caller']); return
        begin_turn(s, s['final_turn_order'][s['final_turn_index']], now)
    else:
        begin_turn(s, next_seat(s, seat), now)


# --- helpers -----------------------------------------------------------------

def slot(s, seat, handle):
    return next((x for x in s['hands'][seat] if x['slot'] == handle), None)


def is_locked(s, seat, entry):
    return entry['locked'] or seat == s['dutch_caller']


def own_unlocked(s, seat, handle):
    entry = slot(s, seat, handle)
    require(entry is not None, 'Choose one of your own cards.')
    require(not is_locked(s, seat, entry), 'That card is locked.')
    return entry


def draw_card(s, rng=None):
    if not s['draw_pile'] and s['rules']['empty_draw_pile'] == 'reshuffle' and len(s['discard_pile']) > 1:
        s['draw_pile'] = s['discard_pile'][:-1]; s['discard_pile'] = s['discard_pile'][-1:]
        (rng or secrets.SystemRandom()).shuffle(s['draw_pile'])
    require(bool(s['draw_pile']), 'No draw cards are available. Take the discard or call Dutch when allowed.')
    return s['draw_pile'].pop()


def open_cut(s):
    if s['status'] == 'playing' and s['discard_pile'] and all(s['first_turn_done']):
        s['cut_window'] = {'event_id': token(), 'rank': s['cards'][s['discard_pile'][-1]]['rank']}
    else:
        s['cut_window'] = None


def do_swap(s, seat, handle, incoming, now, source):
    entry = own_unlocked(s, seat, handle)
    old = entry['card']; entry['card'] = incoming
    s['discard_pile'].append(old); s['reserved'] = None
    s['first_turn_done'][seat] = True
    event(s, 'card.discarded', seat, slot=handle, source=source)
    advance(s, seat, now)
    open_cut(s)


def grant_power(s, seat, card, now):
    """A power card drawn and discarded straight away opens an optional power."""
    kind = POWER_RANKS.get(s['cards'][card]['rank'])
    if kind and s['rules']['powers'].get(kind) and s['hands'][seat]:
        s['power'] = {'seat': seat, 'owner': s['players'][seat]['id'], 'kind': kind, 'step': 'select'}
        s['phase'] = 'power_select'
        return True
    return False


# --- scoring -----------------------------------------------------------------

def hand_total(s, hand):
    return sum(s['rules']['card_values'][s['cards'][x['card']]['rank']] for x in hand)


def finish(s, reason, actor):
    require(s['status'] in ('playing', 'dutch_final'), 'This round is already finished.')
    totals = [hand_total(s, h) for h in s['hands']]
    earned = totals[:]; success = True
    if reason == 'dutch':
        others = [v for i, v in enumerate(totals) if i != actor]
        success = totals[actor] <= min(others) if s['rules']['dutch_tie_counts_as_win'] else totals[actor] < min(others)
        earned[actor] = 0 if success else s['rules']['failed_dutch_multiplier'] * totals[actor]
    else:
        earned[actor] = 0
    s['scores'] = [a + b for a, b in zip(s['scores'], earned)]
    result = {'round': s['round'], 'reason': reason, 'actor': actor, 'success': success,
              'totals': totals, 'earned': earned, 'scores': s['scores'][:],
              'hands': [[copy.deepcopy(s['cards'][x['card']]) for x in h] for h in s['hands']]}
    s['round_result'] = result; s['round_history'].append(copy.deepcopy(result))
    final = s['round'] >= s['rules']['rounds']
    s.update(status='match_results' if final else 'round_results', phase='results', turn=None,
             turn_deadline=None, reserved=None, power=None, cut_window=None, cut_reveal=None, initial_peeks={})
    if final: s['winner_seats'] = [i for i, v in enumerate(s['scores']) if v == min(s['scores'])]
    s['turn_id'] += 1; event(s, 'round.finished', actor, reason=reason)


# --- timers ------------------------------------------------------------------

def tick(s, now, rng=None):
    if s['status'] not in ACTIVE: return
    # setup: reveal-count choice timeout -> random
    if s['status'] == 'choose_reveal' and now >= s['setup_deadline']:
        r = s['rules']; set_reveal_count(s, (rng or secrets.SystemRandom()).randint(r['reveal_min'], r['reveal_max']), now)
    # setup: everyone selects within the window, then all reveals start at once
    if s['status'] == 'initial_peek':
        if s['phase'] == 'select' and now >= s['setup_deadline']:
            fill_reveal(s, now)  # timer up: auto-fill any missing picks, then reveal
        if s['status'] == 'initial_peek' and s['phase'] == 'reveal' and now >= s['peek_reveal_until']:
            begin_play(s, now)
    # active play: jack reveal expiry advances the held turn; turn deadline skips/auto-discards
    if s['status'] in ('playing', 'dutch_final'):
        p = s['power']
        if p and p['kind'] == 'jack' and 'until' in p and now >= p['until']:
            seat = p['seat']; s['power'] = None; advance(s, seat, now)
        if s['cut_reveal'] and now >= s['cut_reveal']['until']: s['cut_reveal'] = None
        if s['turn'] is not None and s['turn_deadline'] is not None and now >= s['turn_deadline']:
            resolve_timeout(s, now)


def resolve_timeout(s, now):
    seat = s['turn']
    if s['reserved'] and s['reserved']['seat'] == seat:
        r = s['reserved']  # auto-discard the drawn card (no power), removing its leftmost slot
        s['hands'][seat] = [x for x in s['hands'][seat] if x['slot'] != r['slot']]
        s['discard_pile'].append(r['card']); s['reserved'] = None
        s['first_turn_done'][seat] = True
        event(s, 'card.discarded', seat, slot=r['slot'], source='timeout')
        advance(s, seat, now); open_cut(s)
    elif s['power'] and s['power']['seat'] == seat:
        s['power'] = None; advance(s, seat, now)
    else:
        s['first_turn_done'][seat] = True
        event(s, 'turn.skipped', seat)
        advance(s, seat, now)


# --- actions -----------------------------------------------------------------

def act(s, seat, action, data, now, rng=None):
    tick(s, now, rng)
    require(type(seat) is int and 0 <= seat < s['player_limit'] and s['players'][seat], 'Join this table first.')

    if action == 'choose_reveal':
        require(s['status'] == 'choose_reveal' and seat == s['chooser'], 'Only the chooser picks the reveal count now.')
        set_reveal_count(s, data.get('count'), now); event(s, 'reveal.chosen', seat, count=s['reveal_count']); return

    if action == 'initial_peek':
        require(s['status'] == 'initial_peek' and s['phase'] == 'select', 'Starting peek is not open.')
        handles = data.get('slots') or []   # live selection; may be partial and may be resubmitted
        require(isinstance(handles, list) and len(handles) <= s['reveal_count'] and len(set(handles)) == len(handles), 'Choose up to your reveal count of distinct cards.')
        entries = [slot(s, seat, h) for h in handles]
        require(all(entries), 'A selected card is no longer in your hand.')
        s['initial_peeks'][str(seat)] = {'owner': s['players'][seat]['id'], 'slots': [copy.deepcopy(e) for e in entries]}
        event(s, 'peek.available', seat)
        if all_full(s): fill_reveal(s, now)  # everyone picked their full count -> reveal now
        return

    require(s['status'] in ('playing', 'dutch_final'), 'Wait for the current phase to finish.')

    # cuts and powers may be issued outside the strict turn gate
    if action == 'cut': return do_cut(s, seat, data, now, rng)
    if action in ('jack_peek', 'queen_swap', 'king_lock', 'power_skip'): return do_power(s, seat, action, data, now)

    # turn-gated plays
    require(seat == s['turn'], 'It is not your turn.')
    require(data.get('turn_id') == s['turn_id'], 'Your table changed. Select the action again.')

    if action == 'swap_drawn':
        # Keep the drawn card (sitting at the leftmost slot) and discard a chosen original.
        r = s['reserved']; require(r and r['owner'] == s['players'][seat]['id'], 'You have no drawn card.')
        entry = own_unlocked(s, seat, data.get('slot'))
        require(entry['slot'] != r['slot'], 'Tap the drawn card itself to discard it.')
        s['hands'][seat] = [x for x in s['hands'][seat] if x['slot'] != entry['slot']]
        s['discard_pile'].append(entry['card']); s['reserved'] = None
        s['first_turn_done'][seat] = True
        event(s, 'card.discarded', seat, slot=entry['slot'], source='draw')
        advance(s, seat, now); open_cut(s); return
    if action == 'discard_drawn':
        do_discard_drawn(s, seat, data, now); return

    require(s['phase'] == 'normal_choice' and s['reserved'] is None and s['power'] is None, 'Finish the pending action first.')
    s['cut_window'] = None  # the turn owner playing closes any open cut window

    if action == 'draw':
        # The drawn card enters the hand at the leftmost slot; the player then picks one to discard.
        card = draw_card(s, rng); handle = token(rng)
        s['hands'][seat].insert(0, {'slot': handle, 'card': card, 'locked': False})
        s['reserved'] = {'owner': s['players'][seat]['id'], 'seat': seat, 'slot': handle, 'card': card, 'until': now + s['rules']['draw_preview_seconds']}
        s['phase'] = 'draw_reveal'; s['turn_id'] += 1; event(s, 'draw.preview', seat, slot=handle); return

    if action == 'take_discard':
        require(bool(s['discard_pile']), 'The discard pile is empty.')
        incoming = s['discard_pile'].pop()
        do_swap(s, seat, data.get('slot'), incoming, now, 'discard'); return

    if action == 'call':
        require(s['status'] == 'playing' and all(s['first_turn_done']), 'Dutch is locked until everyone has played once.')
        order = []; i = next_seat(s, seat)
        while i != seat: order.append(i); i = next_seat(s, i)
        s.update(status='dutch_final', dutch_caller=seat, final_turn_order=order, final_turn_index=0)
        event(s, 'dutch.called', seat); begin_turn(s, order[0], now); return

    raise ValueError('Unknown Dutch action.')


def do_discard_drawn(s, seat, data, now):
    require(s['rules']['allow_discard_drawn'], 'Discarding the drawn card is not allowed.')
    r = s['reserved']; require(r and r['owner'] == s['players'][seat]['id'], 'You have no drawn card to discard.')
    card = r['card']  # remove the drawn card from its leftmost slot and discard it straight away
    s['hands'][seat] = [x for x in s['hands'][seat] if x['slot'] != r['slot']]
    s['discard_pile'].append(card); s['reserved'] = None
    s['first_turn_done'][seat] = True
    event(s, 'card.discarded', seat, slot=r['slot'], source='discard_drawn')
    open_cut(s)
    if not grant_power(s, seat, card, now):
        advance(s, seat, now)


def do_power(s, seat, action, data, now):
    p = s['power']
    require(p and p['seat'] == seat and p['owner'] == s['players'][seat]['id'], 'No power is available.')
    if action == 'power_skip':
        s['power'] = None; advance(s, seat, now); return
    if action == 'jack_peek':
        require(p['kind'] == 'jack' and p['step'] == 'select', 'No Jack peek is available.')
        entry = slot(s, seat, data.get('slot')); require(entry is not None, 'Choose one of your own cards.')
        p.update(step='reveal', slot=entry['slot'], card=entry['card'], until=now + s['rules']['jack_peek_seconds'])
        event(s, 'power.used', seat, power='jack', slot=entry['slot']); return
    if action == 'queen_swap':
        require(p['kind'] == 'queen', 'No Queen swap is available.')
        own = own_unlocked(s, seat, data.get('own_slot'))
        target_seat = data.get('target_seat')
        require(type(target_seat) is int and 0 <= target_seat < s['player_limit'] and target_seat != seat and s['players'][target_seat], 'Choose an opponent.')
        target = slot(s, target_seat, data.get('target_slot'))
        require(target is not None and not is_locked(s, target_seat, target), 'Choose an unlocked opponent card.')
        own['card'], target['card'] = target['card'], own['card']
        s['power'] = None
        event(s, 'power.used', seat, power='queen', slot=own['slot'], target_seat=target_seat, target_slot=target['slot'])
        advance(s, seat, now); return
    if action == 'king_lock':
        require(p['kind'] == 'king', 'No King power is available.')
        target_seat = data.get('target_seat')
        require(type(target_seat) is int and 0 <= target_seat < s['player_limit'] and s['players'][target_seat], 'Choose a player.')
        require(s['rules']['king_target'] == 'any' or target_seat == seat, 'You may only lock your own cards.')
        require(target_seat != s['dutch_caller'], 'A Dutch caller’s hand cannot be locked.')
        entry = slot(s, target_seat, data.get('target_slot')); require(entry is not None, 'Choose a card.')
        mode = data.get('mode')
        if mode == 'lock':
            require(not entry['locked'], 'That card is already locked.'); entry['locked'] = True
        elif mode == 'unlock':
            require(entry['locked'], 'That card is not locked.'); entry['locked'] = False
        else:
            raise ValueError('Choose lock or unlock.')
        s['power'] = None
        event(s, 'power.used', seat, power='king', target_seat=target_seat, target_slot=entry['slot'], mode=mode)
        advance(s, seat, now); return
    raise ValueError('Unknown power action.')


def do_cut(s, seat, data, now, rng):
    require(s['status'] == 'playing' and all(s['first_turn_done']), 'Cutting is locked right now.')
    window = s['cut_window']
    require(window and data.get('event_id') == window['event_id'], 'Cut window closed; no penalty was applied.')
    entry = slot(s, seat, data.get('slot')); require(entry is not None, 'Choose one of your own cards.')
    require(not entry['locked'], 'Locked cards cannot be cut.')
    if s['cards'][entry['card']]['rank'] == window['rank']:
        s['hands'][seat] = [x for x in s['hands'][seat] if x['slot'] != entry['slot']]
        s['discard_pile'].append(entry['card']); s['power'] = None
        event(s, 'cut.accepted', seat, slot=entry['slot'])
        if not s['hands'][seat]: finish(s, 'empty_cut', seat); return
        begin_turn(s, seat, now); open_cut(s) if s['rules']['cut_on_cut_card'] else s.update(cut_window=None)
        return
    # failed cut: card stays in its slot, public 2s reveal, one unseen penalty card from the deck
    s['cut_reveal'] = {'seat': seat, 'slot': entry['slot'], 'face': copy.deepcopy(s['cards'][entry['card']]), 'until': now + s['rules']['failed_cut_reveal_seconds']}
    penalty = None
    if s['draw_pile'] or (s['rules']['empty_draw_pile'] == 'reshuffle' and len(s['discard_pile']) > 1):
        penalty = token(rng); s['hands'][seat].insert(0, {'slot': penalty, 'card': draw_card(s, rng), 'locked': False})  # leftmost, like a draw
    event(s, 'cut.penalty', seat, slot=entry['slot'], penalty=penalty)
    if s['rules']['failed_cutter_takes_next_turn']: begin_turn(s, seat, now)


# --- projection --------------------------------------------------------------

def public(s, viewer, now):
    """Allowlisted per-viewer projection. Faces cross the wire only when public
    (locked cards, round-end reveal) or owned-and-within an active private window."""
    r = s['rules']; own = viewer is not None; results = s['status'] in RESULTS

    def face(entry):
        return copy.deepcopy(s['cards'][entry['card']]) if (entry['locked'] or results) else None

    result = {k: copy.deepcopy(s[k]) for k in (
        'game_type', 'status', 'phase', 'player_limit', 'host', 'round', 'max_rounds', 'scores',
        'turn', 'turn_id', 'turn_deadline', 'setup_deadline', 'chooser', 'reveal_count', 'starter',
        'dutch_caller', 'final_turn_order', 'final_turn_index', 'round_result', 'round_history',
        'winner_seats', 'revision', 'event', 'first_turn_done')}
    result.update(
        server_now=now, seat=viewer, rules=copy.deepcopy(r),
        players=[{k: p.get(k) for k in ('name', 'avatar', 'ready', 'connected')} if p else None for p in s['players']],
        counts=[len(h) for h in s['hands']],
        hands=[[{'slot': x['slot'], 'locked': x['locked'], 'face': face(x)} for x in h] for h in s['hands']],
        draw_count=len(s['draw_pile']),
        can_draw=bool(s['draw_pile'] or (r['empty_draw_pile'] == 'reshuffle' and len(s['discard_pile']) > 1)),
        discard=copy.deepcopy(s['cards'][s['discard_pile'][-1]]) if s['discard_pile'] else None,
        unlocked=bool(s['first_turn_done'] and all(s['first_turn_done'])),
        cut=({'event_id': s['cut_window']['event_id'], 'rank': s['cut_window']['rank']} if s['cut_window'] else None),
        cut_reveal=copy.deepcopy(s['cut_reveal']) if s['cut_reveal'] else None,
        reveals={}, drawn=None, power=None,
        initial_selected=bool(own and len(s['initial_peeks'].get(str(viewer), {}).get('slots', [])) == s['reveal_count']),
        can_call=bool(own and s['status'] == 'playing' and viewer == s['turn'] and s['phase'] == 'normal_choice'
                      and all(s['first_turn_done']) and s['reserved'] is None and s['power'] is None))

    if own and s['status'] in ACTIVE:
        ident = s['players'][viewer]['id']
        # starting peek: faces appear only during the shared reveal phase, each viewer own-only
        peek = s['initial_peeks'].get(str(viewer))
        if peek and peek['owner'] == ident and s['phase'] == 'reveal' and peek.get('until') and now < peek['until']:
            for x in peek['slots']:
                cur = slot(s, viewer, x['slot'])
                if cur:
                    result['reveals'][x['slot']] = {'face': copy.deepcopy(s['cards'][cur['card']]), 'until': peek['until']}
        p = s['power']
        if p and p['seat'] == viewer and p['owner'] == ident:
            result['power'] = {'kind': p['kind'], 'step': p['step']}
            if p['kind'] == 'jack' and p.get('step') == 'reveal' and now < p['until']:
                cur = slot(s, viewer, p['slot'])
                if cur and cur['card'] == p['card']:
                    result['reveals'][p['slot']] = {'face': copy.deepcopy(s['cards'][p['card']]), 'until': p['until']}
        held = s['reserved']  # the drawn card sits at its leftmost slot; show it face-up to its owner for 3s
        if held and held['seat'] == viewer and held['owner'] == ident:
            visible = now < held['until']
            result['drawn'] = {'slot': held['slot'], 'until': held['until'], 'face': copy.deepcopy(s['cards'][held['card']]) if visible else None}
            if visible:
                result['reveals'][held['slot']] = {'face': copy.deepcopy(s['cards'][held['card']]), 'until': held['until']}
    return result
