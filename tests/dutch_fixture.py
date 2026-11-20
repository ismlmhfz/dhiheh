"""Deterministic browser fixtures, strictly restricted to an isolated SQLite DB."""
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ten.settings')
import django
django.setup()
from django.conf import settings
from django.db import transaction
from game.models import Room
from game import dutch_engine as e
assert settings.DEBUG and str(settings.DATABASES['default']['NAME']).endswith('/dutch-browser.sqlite3'), 'Fixture requires isolated dutch-browser.sqlite3'
code, kind = sys.argv[1:]
with transaction.atomic():
    room = Room.objects.select_for_update().get(code=code); s = room.state
    assert s['game_type'] == 'dutch'
    # (hands per seat, discard top, draw-pile top rank). Suits are arbitrary; cut matches rank only.
    layouts = {
        'cut':   ([['2C', '3C', '4C', '5C'], ['6C', '7C', '8C', '9C']], '2S', None, 1),   # seat 0 cuts its 2C
        'bad':   ([['3C', '4C', '5C', '6C'], ['7C', '8C', '9C', '10C']], '2S', None, 1),   # seat 0 cuts a wrong rank
        'empty': ([['2C'], ['6C', '7C', '8C', '9C']], '2S', None, 1),                      # seat 0 cuts its last card
        'queen': ([['3C','4C','5C','6C'],['7C','8C','9C','10C']], '2S', 'QD', 0),
        'jack': ([['3C','4C','5C','6C'],['7C','8C','9C','10C']], '2S', 'JD', 0),
        'king':  ([['3C', '4C', '5C', '6C'], ['7C', '8C', '9C', '10C']], '2S', 'KD', 0),   # seat 0 draws+discards a King
    }
    hands, top, draw_top, turn = layouts[kind]
    remaining = list(s['cards'])

    def get(face):
        cid = next(c for c in remaining if s['cards'][c]['rank'] + s['cards'][c]['suit'] == face)
        remaining.remove(cid); return cid

    s['hands'] = [[{'slot': e.token(), 'card': get(card), 'locked': False} for card in hand] for hand in hands]
    s['discard_pile'] = [get(top)]
    if draw_top:  # draw_card pops the last element, so the intended card goes last
        tid = get(draw_top); remaining.append(tid)
    s['draw_pile'] = remaining
    s.update(status='playing', phase='normal_choice', turn=turn, first_turn_done=[True, True],
             initial_peeks={}, peek_reveal_until=None, reserved=None, power=None,
             cut_window=None, cut_reveal=None, round_result=None,
             turn_deadline=time.time() + 300)
    if kind not in ('king','queen','jack'):
        e.open_cut(s)
    s['turn_id'] += 1; s['revision'] += 1; e.event(s, 'fixture.' + kind)
    room.save(update_fields=['state'])
