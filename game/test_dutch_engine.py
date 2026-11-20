import random
from django.test import SimpleTestCase
from . import dutch_engine as e


def seated(n):
    s = e.new_state(n, '0', 'P0', 0.0)
    for i in range(1, n):
        s['players'][i] = {'id': str(i), 'name': f'P{i}', 'ready': True, 'connected': True, 'connections': {}}
    for p in s['players']:
        p['ready'] = True; p['connected'] = True
    return s


def rigged(ranks_per_seat, discard='2', now=0.0, unlocked=True, draw_ranks=()):
    """Build a playing state with controlled ranks. Suits are arbitrary (cut matches rank)."""
    n = len(ranks_per_seat)
    s = seated(n)
    s['rules']  # frozen defaults
    cards, hands = {}, []
    cid = 0
    for seat, ranks in enumerate(ranks_per_seat):
        hand = []
        for j, r in enumerate(ranks):
            key = f'c{cid}'; cards[key] = {'rank': r, 'suit': 'S'}; cid += 1
            hand.append({'slot': f's{seat}_{j}', 'card': key, 'locked': False})
        hands.append(hand)
    dkey = f'c{cid}'; cards[dkey] = {'rank': discard, 'suit': 'H'}; cid += 1
    draw = []
    for r in draw_ranks:
        key = f'c{cid}'; cards[key] = {'rank': r, 'suit': 'D'}; cid += 1; draw.append(key)
    s.update(cards=cards, hands=hands, discard_pile=[dkey], draw_pile=draw,
             status='playing', phase='normal_choice', round=1, chooser=0, starter=0,
             turn=0, turn_id=5, turn_deadline=now + 30, first_turn_done=[unlocked] * n)
    return s


def card_ids(s):
    # A drawn card lives at its leftmost hand slot, so hands already include it.
    return [x['card'] for h in s['hands'] for x in h] + s['draw_pile'] + s['discard_pile']


class SetupTests(SimpleTestCase):
    def test_deal_and_piles(self):
        for n in (2, 3, 4, 5, 6):
            s = seated(n); e.start(s, 0, 0.0, random.Random(n))
            self.assertEqual(len(s['cards']), 52)
            self.assertEqual(len(set(card_ids(s))), 52)
            self.assertTrue(all(len(h) == 4 for h in s['hands']))
            self.assertEqual(len(s['discard_pile']), 1)
            self.assertEqual(len(s['draw_pile']), 52 - 4 * n - 1)
            self.assertEqual(s['status'], 'choose_reveal')
            self.assertEqual(s['chooser'], 0)

    def test_chooser_rotates_right(self):
        s = seated(4); e.start(s, 0, 0.0, random.Random(1))
        self.assertEqual(s['chooser'], 0)
        # force to round_results then advance
        for rnd in range(2, 5):
            s['status'] = 'round_results'
            e.next_round(s, 0.0, random.Random(rnd))
            self.assertEqual(s['chooser'], (rnd - 1) % 4)

    def test_reveal_zero_starts_play_immediately(self):
        s = seated(3); e.start(s, 0, 0.0, random.Random(2))
        e.act(s, 0, 'choose_reveal', {'count': 0}, 0.0)
        self.assertEqual(s['status'], 'playing')
        self.assertEqual(s['turn'], s['chooser'])

    def test_only_chooser_picks(self):
        s = seated(3); e.start(s, 0, 0.0, random.Random(3))
        with self.assertRaises(ValueError):
            e.act(s, 1, 'choose_reveal', {'count': 2}, 0.0)

    def test_select_then_shared_reveal(self):
        s = seated(2); e.start(s, 0, 0.0, random.Random(4))
        e.act(s, 0, 'choose_reveal', {'count': 2}, 0.0)
        self.assertEqual((s['status'], s['phase']), ('initial_peek', 'select'))
        chosen = [s['hands'][0][0]['slot'], s['hands'][0][1]['slot']]
        e.act(s, 0, 'initial_peek', {'slots': chosen}, 1.0)
        self.assertIn('0', s['initial_peeks'])
        self.assertIsNone(s['peek_reveal_until'])            # no reveal until everyone selects
        # seat 1 never selects; the 10 s select window passes -> auto-pick, then shared reveal
        e.tick(s, 11.0, random.Random(5))
        self.assertEqual(s['phase'], 'reveal')
        self.assertIn('1', s['initial_peeks'])
        self.assertTrue(e.public(s, 0, 11.0)['reveals'])     # everyone sees their own at once
        self.assertFalse(e.public(s, 1, 11.0)['reveals'].keys() & e.public(s, 0, 11.0)['reveals'].keys())
        e.tick(s, 15.0, random.Random(6))                    # reveal (3 s) ends -> play
        self.assertEqual(s['status'], 'playing')

    def test_last_selector_starts_reveal_at_once(self):
        s = seated(2); e.start(s, 0, 0.0, random.Random(7))
        e.act(s, 0, 'choose_reveal', {'count': 1}, 0.0)
        e.act(s, 0, 'initial_peek', {'slots': [s['hands'][0][0]['slot']]}, 0.5)
        self.assertEqual(s['phase'], 'select')
        e.act(s, 1, 'initial_peek', {'slots': [s['hands'][1][0]['slot']]}, 0.6)
        self.assertEqual(s['phase'], 'reveal')               # last to choose triggers the reveal


class TurnTests(SimpleTestCase):
    def test_draw_enters_leftmost_then_keep_discards_an_original(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2', '2', '2', '2']], draw_ranks=['9'])
        original = s['hands'][0][0]['slot']
        e.act(s, 0, 'draw', {'turn_id': s['turn_id']}, 0.0)
        self.assertEqual(s['phase'], 'draw_reveal')
        self.assertEqual(s['hands'][0][0]['slot'], s['reserved']['slot'])     # drawn sits leftmost
        self.assertEqual(s['cards'][s['hands'][0][0]['card']]['rank'], '9')
        self.assertEqual(len(s['hands'][0]), 5)
        # keep the draw: discard an original card; the drawn card stays at leftmost
        e.act(s, 0, 'swap_drawn', {'slot': original, 'turn_id': s['turn_id']}, 1.0)
        self.assertEqual(s['cards'][s['discard_pile'][-1]]['rank'], 'A')
        self.assertEqual(s['cards'][s['hands'][0][0]['card']]['rank'], '9')   # drawn kept, still leftmost
        self.assertEqual(len(s['hands'][0]), 4)
        self.assertEqual(s['turn'], 1)
        self.assertTrue(s['first_turn_done'][0])

    def test_discard_drawn_removes_leftmost(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2', '2', '2', '2']], draw_ranks=['9'])
        e.act(s, 0, 'draw', {'turn_id': s['turn_id']}, 0.0)
        e.act(s, 0, 'discard_drawn', {'turn_id': s['turn_id']}, 1.0)
        self.assertEqual(s['cards'][s['discard_pile'][-1]]['rank'], '9')      # the drawn card itself
        self.assertEqual(len(s['hands'][0]), 4)
        self.assertTrue(all(s['cards'][x['card']]['rank'] == 'A' for x in s['hands'][0]))

    def test_take_discard_swaps(self):
        s = rigged([['K', 'K', 'K', 'K'], ['3', '3', '3', '3']], discard='7')
        target = s['hands'][0][0]['slot']
        e.act(s, 0, 'take_discard', {'slot': target, 'turn_id': s['turn_id']}, 0.0)
        self.assertEqual(s['cards'][e.slot(s, 0, target)['card']]['rank'], '7')
        self.assertEqual(s['cards'][s['discard_pile'][-1]]['rank'], 'K')
        self.assertEqual(s['turn'], 1)

    def test_timeout_before_draw_skips(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2', '2', '2', '2']])
        e.tick(s, 31.0)
        self.assertTrue(s['first_turn_done'][0])
        self.assertEqual(s['turn'], 1)

    def test_timeout_after_draw_autodiscards_no_power(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2', '2', '2', '2']], draw_ranks=['J'])
        e.act(s, 0, 'draw', {'turn_id': s['turn_id']}, 0.0)
        e.tick(s, 31.0)
        self.assertEqual(s['cards'][s['discard_pile'][-1]]['rank'], 'J')
        self.assertEqual(len(s['hands'][0]), 4)         # drawn leftmost removed
        self.assertIsNone(s['power'])                   # auto-discarded Jack grants no power
        self.assertEqual(s['turn'], 1)


class PowerTests(SimpleTestCase):
    def test_jack_peek_then_advances(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2', '2', '2', '2']], draw_ranks=['J'])
        e.act(s, 0, 'draw', {'turn_id': s['turn_id']}, 0.0)
        e.act(s, 0, 'discard_drawn', {'turn_id': s['turn_id']}, 1.0)
        self.assertEqual(s['power']['kind'], 'jack')
        own = s['hands'][0][0]['slot']
        e.act(s, 0, 'jack_peek', {'slot': own}, 1.0)
        pub = e.public(s, 0, 1.0)
        self.assertIn(own, pub['reveals'])  # owner sees it for 1s
        self.assertNotIn(own, e.public(s, 1, 1.0)['reveals'])  # opponent does not
        e.tick(s, 2.5)
        self.assertIsNone(s['power'])
        self.assertEqual(s['turn'], 1)

    def test_queen_swaps_cards_between_hands(self):
        s = rigged([['A', '5', '5', '5'], ['9', '2', '2', '2']], draw_ranks=['Q'])
        own = s['hands'][0][0]['slot']; opp = s['hands'][1][0]['slot']
        e.act(s, 0, 'draw', {'turn_id': s['turn_id']}, 0.0)
        e.act(s, 0, 'discard_drawn', {'turn_id': s['turn_id']}, 1.0)
        e.act(s, 0, 'queen_swap', {'own_slot': own, 'target_seat': 1, 'target_slot': opp}, 1.0)
        self.assertEqual(s['cards'][e.slot(s, 0, own)['card']]['rank'], '9')
        self.assertEqual(s['cards'][e.slot(s, 1, opp)['card']]['rank'], 'A')
        self.assertEqual(s['turn'], 1)

    def test_king_lock_makes_face_public_and_blocks_swap(self):
        s = rigged([['A', '5', '5', '5'], ['9', '2', '2', '2']], draw_ranks=['K'])
        own = s['hands'][0][1]['slot']
        e.act(s, 0, 'draw', {'turn_id': s['turn_id']}, 0.0)
        e.act(s, 0, 'discard_drawn', {'turn_id': s['turn_id']}, 1.0)
        e.act(s, 0, 'king_lock', {'target_seat': 0, 'target_slot': own, 'mode': 'lock'}, 1.0)
        self.assertTrue(e.slot(s, 0, own)['locked'])
        # locked face is public to everyone
        self.assertIsNotNone(next(c for c in e.public(s, 1, 1.0)['hands'][0] if c['slot'] == own)['face'])
        # cannot swap or take-discard into a locked slot
        s['turn'] = 0; s['phase'] = 'normal_choice'; s['reserved'] = None; s['power'] = None
        s['turn_id'] += 1; s['turn_deadline'] = 40
        with self.assertRaises(ValueError):
            e.act(s, 0, 'take_discard', {'slot': own, 'turn_id': s['turn_id']}, 2.0)

    def test_king_cannot_lock_dutch_caller(self):
        s = rigged([['A', '5', '5', '5'], ['9', '2', '2', '2']], draw_ranks=['K'])
        s['dutch_caller'] = 1
        e.act(s, 0, 'draw', {'turn_id': s['turn_id']}, 0.0)
        e.act(s, 0, 'discard_drawn', {'turn_id': s['turn_id']}, 1.0)
        with self.assertRaises(ValueError):
            e.act(s, 0, 'king_lock', {'target_seat': 1, 'target_slot': s['hands'][1][0]['slot'], 'mode': 'lock'}, 1.0)


class CutTests(SimpleTestCase):
    def test_locked_until_first_turns(self):
        s = rigged([['2', 'A', 'A', 'A'], ['2', '3', '3', '3']], discard='2', unlocked=False)
        s['cut_window'] = None
        with self.assertRaises(ValueError):
            e.act(s, 1, 'cut', {'slot': s['hands'][1][0]['slot'], 'event_id': 'x'}, 0.0)

    def test_successful_cut_takes_turn(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2', '3', '3', '3']], discard='2')
        e.open_cut(s)
        ev = s['cut_window']['event_id']; cut_slot = s['hands'][1][0]['slot']
        e.act(s, 1, 'cut', {'slot': cut_slot, 'event_id': ev}, 0.0)
        self.assertEqual(len(s['hands'][1]), 3)
        self.assertEqual(s['turn'], 1)
        self.assertEqual(s['cards'][s['discard_pile'][-1]]['rank'], '2')

    def test_failed_cut_penalty_and_turn_unchanged(self):
        s = rigged([['A', 'A', 'A', 'A'], ['9', '3', '3', '3']], discard='2', draw_ranks=['6'])
        e.open_cut(s); ev = s['cut_window']['event_id']
        before = len(s['hands'][1]); bad = s['hands'][1][0]['slot']
        e.act(s, 1, 'cut', {'slot': bad, 'event_id': ev}, 0.0)
        self.assertEqual(len(s['hands'][1]), before + 1)      # one penalty card
        self.assertIsNotNone(s['cut_reveal'])                 # public reveal
        self.assertEqual(s['turn'], 0)                        # order unchanged
        e.tick(s, 2.5)
        self.assertIsNone(s['cut_reveal'])

    def test_empty_hand_cut_ends_round(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2']], discard='2')
        e.open_cut(s); ev = s['cut_window']['event_id']
        e.act(s, 1, 'cut', {'slot': s['hands'][1][0]['slot'], 'event_id': ev}, 0.0)
        self.assertEqual(s['status'], 'round_results')
        self.assertEqual(s['round_result']['reason'], 'empty_cut')
        self.assertEqual(s['round_result']['earned'][1], 0)

    def test_cannot_cut_locked_card(self):
        s = rigged([['A', 'A', 'A', 'A'], ['2', '3', '3', '3']], discard='2')
        s['hands'][1][0]['locked'] = True
        e.open_cut(s); ev = s['cut_window']['event_id']
        with self.assertRaises(ValueError):
            e.act(s, 1, 'cut', {'slot': s['hands'][1][0]['slot'], 'event_id': ev}, 0.0)


class DutchTests(SimpleTestCase):
    def test_call_builds_final_order(self):
        s = rigged([['A', 'A'], ['5', '5'], ['6', '6']], discard='2')
        e.act(s, 0, 'call', {'turn_id': s['turn_id']}, 0.0)
        self.assertEqual(s['status'], 'dutch_final')
        self.assertEqual(s['final_turn_order'], [1, 2])
        self.assertEqual(s['turn'], 1)

    def test_successful_dutch_scores_zero(self):
        s = rigged([['A', 'A'], ['9', '9'], ['9', '9']], discard='2')  # caller total 2, others 18
        e.act(s, 0, 'call', {'turn_id': s['turn_id']}, 0.0)
        # each opponent takes a trivial turn (draw+discard same via timeout skip)
        e.tick(s, 31.0); e.tick(s, 62.0)
        self.assertEqual(s['status'], 'round_results')
        self.assertEqual(s['round_result']['earned'][0], 0)
        self.assertTrue(s['round_result']['success'])

    def test_tie_fails_doubles_caller(self):
        s = rigged([['3', '4'], ['7'], ['9']], discard='2')  # caller total 7, opp1 total 7 -> tie fails
        e.act(s, 0, 'call', {'turn_id': s['turn_id']}, 0.0)
        e.tick(s, 31.0); e.tick(s, 62.0)
        self.assertFalse(s['round_result']['success'])
        self.assertEqual(s['round_result']['earned'][0], 14)

    def test_no_cut_during_final(self):
        s = rigged([['A', 'A'], ['2', '5'], ['6', '6']], discard='2')
        e.act(s, 0, 'call', {'turn_id': s['turn_id']}, 0.0)
        with self.assertRaises(ValueError):
            e.act(s, 1, 'cut', {'slot': s['hands'][1][0]['slot'], 'event_id': 'x'}, 1.0)


class MatchTests(SimpleTestCase):
    def test_tenth_round_finishes_match(self):
        s = rigged([['2'], ['9']], discard='2')
        s['round'] = 10
        e.open_cut(s); ev = s['cut_window']['event_id']
        e.act(s, 0, 'cut', {'slot': s['hands'][0][0]['slot'], 'event_id': ev}, 0.0)
        self.assertEqual(s['status'], 'match_results')
        self.assertEqual(s['winner_seats'], [0])

    def test_conservation_through_a_round(self):
        s = seated(3); e.start(s, 0, 0.0, random.Random(99))
        e.act(s, 0, 'choose_reveal', {'count': 1}, 0.0)
        e.tick(s, 11.0, random.Random(1))   # select window closes -> auto-pick + shared reveal
        e.tick(s, 15.0, random.Random(1))   # reveal ends -> play
        self.assertEqual(s['status'], 'playing')
        self.assertEqual(len(set(card_ids(s))), 52)


class ProjectionTests(SimpleTestCase):
    def test_opponent_faces_hidden(self):
        s = rigged([['A', 'K', '5', '7'], ['2', '3', '9', 'Q']], discard='2')
        pub = e.public(s, 0, 0.0)
        self.assertTrue(all(c['face'] is None for c in pub['hands'][1]))  # opponent hidden
        self.assertTrue(all(c['face'] is None for c in pub['hands'][0]))  # own also hidden (no active peek)
        self.assertEqual(pub['counts'], [4, 4])
        self.assertNotIn('cards', pub)
        self.assertNotIn('draw_pile', pub)

    def test_round_end_reveals_all(self):
        s = rigged([['A'], ['9']], discard='A')
        e.open_cut(s); ev = s['cut_window']['event_id']
        e.act(s, 0, 'cut', {'slot': s['hands'][0][0]['slot'], 'event_id': ev}, 0.0)
        pub = e.public(s, 1, 0.0)
        self.assertEqual(s['status'], 'round_results')
        self.assertIsNotNone(pub['round_result'])

class AnimationProjectionTests(SimpleTestCase):
    def test_final_cut_keeps_only_public_motion_metadata(self):
        s=rigged([['2'],['3']],discard='2');e.open_cut(s)
        e.act(s,0,'cut',{'slot':'s0_0','event_id':s['cut_window']['event_id']},1)
        view=e.public(s,None,1)
        self.assertEqual(view['event']['kind'],'round.finished')
        self.assertEqual(view['event']['last_move'],{'kind':'cut.accepted','seat':0,'slot':'s0_0'})
        self.assertEqual(view['status'],'round_results')
    def test_failed_cut_face_expires_without_a_timer_tick(self):
        s=rigged([['3'],['4']],discard='2',draw_ranks=['5']);e.open_cut(s)
        e.act(s,0,'cut',{'slot':'s0_0','event_id':s['cut_window']['event_id']},1)
        self.assertIsNotNone(e.public(s,None,2.99)['cut_reveal'])
        self.assertIsNone(e.public(s,None,3)['cut_reveal'])
