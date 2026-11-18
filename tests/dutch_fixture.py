"""Deterministic browser fixtures, strictly restricted to an isolated SQLite DB."""
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','ten.settings')
import django
django.setup()
from django.conf import settings
from django.db import transaction
from game.models import Room
from game import dutch_engine as e
assert settings.DEBUG and str(settings.DATABASES['default']['NAME']).endswith('/dutch-browser.sqlite3'), 'Fixture requires isolated dutch-browser.sqlite3'
code,kind=sys.argv[1:]
with transaction.atomic():
 room=Room.objects.select_for_update().get(code=code);s=room.state
 assert s['game_type']=='dutch'
 layouts={'multi':([['2C','2D','2H','AC'],['3C','4C','5C','6C']],'2S'),
          'bad':([['2C','3C','4C','5C'],['6C','7C','8C','9C']],'2S'),
          'jack':([['JC','3C','4C','5C'],['6C','7C','8C','9C']],'AS'),
          'empty':([['JC','JD'],['4C','5C','6C','7C']],'JS')}
 hands,top=layouts[kind];remaining=list(s['cards'])
 def get(face):
  cid=next(c for c in remaining if s['cards'][c]['rank']+s['cards'][c]['suit']==face);remaining.remove(cid);return cid
 s['hands']=[[{'slot':e.token(),'card':get(card)} for card in hand] for hand in hands]
 s['discard_pile']=[get(top)];s['draw_pile']=remaining
 s.update(status='playing',phase='normal_choice',turn=0 if kind=='jack' else 1,first_turn_done=[True,True],initial_peeks={},initial_peeks_done=[True,True],reserved=None,jack_peeks={},cut_window=None,paused=False,round_result=None)
 if kind!='jack':e.open_cut(s,time.time())
 s['turn_id']+=1;s['revision']+=1;e.event(s,'fixture.'+kind)
 room.save(update_fields=['state'])
