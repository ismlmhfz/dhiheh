"""PostgreSQL row-lock races; intentionally bypass the per-process convenience lock."""
import time,uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection,close_old_connections
from django.test import TransactionTestCase
from . import dutch_service as d, dutch_engine as e
from .models import Room

@skipUnless(connection.vendor=='postgresql','Real row-lock concurrency requires PostgreSQL')
class DutchConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.code=d.create('a','A',2)['code'];d.mutate(self.code,'b','join',{'name':'B'})
        for who in ['a','b']:
            d.mutate(self.code,who,'connect',channel=who)
            d.mutate(self.code,who,'ready',{'command':str(uuid.uuid4())})
        d.mutate(self.code,'a','start',{'command':str(uuid.uuid4())})
        room=Room.objects.get(code=self.code);s=room.state
        s.update(status='playing',phase='normal_choice',turn=0,turn_deadline=time.time()+30,
                 first_turn_done=[True,True],initial_peeks={},initial_peeks_done=[True,True])
        # make both players' first card match the discard rank so both cuts are valid for the race
        rank=s['cards'][s['discard_pile'][-1]]['rank']
        for i in (0,1):s['cards'][s['hands'][i][0]['card']]['rank']=rank
        e.open_cut(s);room.save()
        self.s=s
    def race(self,calls):
        barrier=Barrier(len(calls))
        def run(call):
            close_old_connections();barrier.wait()
            try:return d.mutate.__wrapped__(self.code,*call)
            except ValueError as error:return str(error)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=len(calls)) as pool:return list(pool.map(run,calls))
    def conserved(self):
        s=Room.objects.get(code=self.code).state
        ids=[x['card'] for h in s['hands'] for x in h]+s['draw_pile']+s['discard_pile']
        self.assertEqual(len(ids),52);self.assertEqual(len(set(ids)),52)
        return s
    def test_simultaneous_cut_only_one_claim(self):
        calls=[(who,'cut',{'command':str(uuid.uuid4()),'slot':self.s['hands'][i][0]['slot'],'event_id':self.s['cut_window']['event_id']}) for i,who in enumerate(['a','b'])]
        results=self.race(calls)
        self.assertEqual(sum(isinstance(r,dict) for r in results),1)
        self.assertIn('Cut window closed',next(r for r in results if isinstance(r,str)));self.conserved()
    def test_duplicate_draw_across_workers_reserves_one_card(self):
        room=Room.objects.get(code=self.code);room.state['cut_window']=None;room.state['phase']='normal_choice';room.save()
        who=['a','b'][self.s['turn']];data={'command':str(uuid.uuid4()),'turn_id':self.s['turn_id']}
        results=self.race([(who,'draw',data),(who,'draw',data)])
        self.assertTrue(all(isinstance(r,dict) for r in results));s=self.conserved()
        self.assertEqual(len(s['draw_pile']),len(self.s['draw_pile'])-1)
    def test_racing_swaps_only_one_moves(self):
        room=Room.objects.get(code=self.code);room.state['cut_window']=None;room.state['phase']='normal_choice';room.save()
        seat=self.s['turn'];who=['a','b'][seat]
        calls=[(who,'take_discard',{'command':str(uuid.uuid4()),'turn_id':self.s['turn_id'],'slot':self.s['hands'][seat][i]['slot']}) for i in [0,1]]
        results=self.race(calls);self.assertEqual(sum(isinstance(r,dict) for r in results),1);self.conserved()
