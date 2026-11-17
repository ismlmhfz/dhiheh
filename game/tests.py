import copy, time
from unittest.mock import patch
from django.test import TestCase, Client
from . import engine as e, service
from .models import Room
class EngineTests(TestCase):
    def setUp(self):
        self.s={'players':[{'id':str(i),'name':str(i),'ready':True,'connected':True} for i in range(4)],'mode':'standard'}
        e.new_match(self.s)
    def position(self,hands,designated=3):
        self.s.update(hands=hands,turn=0,starter=0,designated=designated,trick=[],trump=None)
    def play_stack(self,cards):
        for seat in (0,3,2,1): e.play(self.s,seat,cards[seat])
    def test_deck_and_private_state(self):
        cards=sum(self.s['hands'],[])
        self.assertEqual(len(set(cards)),52)
        self.assertEqual([len(x) for x in self.s['hands']],[13]*4)
        public=e.public(self.s,0)
        self.assertNotIn('hands',public)
        self.assertNotIn('id',public['players'][1])
        self.assertEqual(public['hand'],self.s['hands'][0])
    def test_turn_ownership_and_follow_suit(self):
        self.position([['2H'],['5H'],['4H'],['3H','AS']])
        with self.assertRaises(ValueError): e.play(self.s,1,'3H')
        with self.assertRaises(ValueError): e.play(self.s,0,'AH')
        e.play(self.s,0,'2H')
        self.assertIsNone(self.s['trump'])
        with self.assertRaises(ValueError): e.play(self.s,3,'AS')
        e.play(self.s,3,'3H')
    def test_dynamic_trump_and_rotation(self):
        self.position([['AH'],['2S'],['AC'],['3S']])
        self.play_stack(['AH','2S','AC','3S'])
        self.assertEqual(self.s['trump'],'S')
        self.assertEqual(self.s['last']['winner'],3)
        self.assertEqual(self.s['starter'],3)
        self.assertEqual(self.s['turn'],3)
        with patch('game.engine.secrets.randbelow',return_value=2):
            e.new_deal(self.s)
        self.assertEqual(self.s['starter'],2)
        self.assertEqual(self.s['turn'],2)
        self.assertIsNone(self.s['trump'])
    def test_winner_leads_even_when_not_designated(self):
        self.position([['2H'],['AH'],['3H'],['4H']],3)
        self.play_stack(['2H','AH','3H','4H'])
        self.assertEqual(self.s['starter'],1)
        self.assertEqual(self.s['turn'],1)
        self.assertEqual(self.s['designated'],3)
    def test_every_seat_winner_leads_next_stack(self):
        for winner in range(4):
            self.setUp()
            cards=['AH' if i==winner else str(i+2)+'H' for i in range(4)]
            self.position([[c,'2C'] for c in cards])
            self.play_stack(cards)
            self.assertEqual(self.s['turn'],winner)
            self.assertEqual(self.s['starter'],winner)
            e.play(self.s,winner,'2C')
            self.assertEqual(self.s['turn'],(winner-1)%4)
    def test_categories(self):
        for tens,stacks,result in [(2,6,0),(2,7,2),(3,1,3),(4,1,5)]:
            self.assertEqual(e.points(tens,stacks),result)
    def test_counterclockwise_transition_skips_players_already_in_stack(self):
        self.assertEqual(e.next_turn([{'seat':0},{'seat':1}]),3)
        self.assertEqual(e.next_turn([{'seat':0},{'seat':1},{'seat':3}]),2)
    def test_failed_chase_keeps_locked_score(self):
        self.position([['2H'],['AH'],['3H'],['10H']])
        self.s.update(chase={'team':0,'locked':2},tens=[['S','D','C'],[]],stacks=[8,1])
        self.play_stack(['2H','AH','3H','10H'])
        self.assertEqual(self.s['scores'],[2,0])
        self.assertEqual(self.s['status'],'deal_results')
        with self.assertRaises(ValueError): e.play(self.s,0,'2H')
    def test_successful_chase(self):
        self.position([['AH'],['2H'],['3H'],['10H']])
        self.s.update(chase={'team':0,'locked':2},tens=[['S','D','C'],[]],stacks=[8,1])
        self.play_stack(['AH','2H','3H','10H'])
        self.assertEqual(self.s['scores'],[5,0])
    def test_chase_offer_and_timeout(self):
        self.position([['AH'],['10H'],['2H'],['3H']])
        self.s.update(tens=[['S','D'],[]])
        self.play_stack(['AH','10H','2H','3H'])
        self.assertEqual(self.s['status'],'chase_decision')
        self.s['decision']['deadline']=time.time()-1
        e.tick(self.s)
        self.assertEqual(self.s['scores'],[3,0])
    def test_opponents_ten_prevents_chase(self):
        self.position([['AH'],['10H'],['2H'],['3H']])
        self.s.update(tens=[['S','D'],['C']])
        self.play_stack(['AH','10H','2H','3H'])
        self.assertEqual(self.s['status'],'deal_results')
    def test_match_target_limit_and_tie(self):
        self.s['scores']=[10,0];e.finish(self.s,0,2)
        self.assertEqual(self.s['winner'],0)
        self.assertEqual(self.s['status'],'match_results')
        self.setUp();self.s.update(deal=7,scores=[0,2],totals_tens=[3,0]);e.finish(self.s,0,2)
        self.assertEqual(self.s['winner'],0)
    def test_full_matches_legal_simulation(self):
        for _ in range(20):
            self.setUp()
            for step in range(1000):
                s=self.s
                if s['status']=='match_results': break
                if s['status']=='deal_results': e.new_deal(s)
                elif s['status']=='chase_decision': e.decide(s,True)
                else:
                    lead=s['trick'][0]['card'][-1] if s['trick'] else None
                    e.play(s,s['turn'],e.legal(s['hands'][s['turn']],lead)[0])
            self.assertEqual(self.s['status'],'match_results')
class RoomTests(TestCase):
    def setUp(self): self.code,_=service.create('p0','Host','quick')
    def join_all(self):
        for i in range(1,4): service.mutate(self.code,f'p{i}','join',{'name':f'P{i}'})
        for i in range(4): service.mutate(self.code,f'p{i}','ready')
    def test_four_ready_required_and_duplicate_commands(self):
        with self.assertRaises(ValueError): service.mutate(self.code,'p0','start')
        self.join_all();service.mutate(self.code,'p0','start')
        with self.assertRaises(ValueError): service.mutate(self.code,'extra','join')
        s=Room.objects.get(code=self.code).state;seat=s['turn'];c=e.public(s,seat)['legal'][0]
        service.mutate(self.code,f'p{seat}','play',{'card':c,'command':'unique'})
        service.mutate(self.code,f'p{seat}','play',{'card':c,'command':'unique'})
        self.assertEqual(len(Room.objects.get(code=self.code).state['trick']),1)
    def test_disconnect_reconnect_and_abandon(self):
        self.join_all();service.mutate(self.code,'p0','start')
        before=service.mutate(self.code,'p0','connect')['hand']
        s=service.mutate(self.code,'p0','disconnect');self.assertTrue(s['paused'])
        s=service.mutate(self.code,'p0','connect');self.assertFalse(s['paused']);self.assertEqual(s['hand'],before)
        s=service.mutate(self.code,'p1','quit');self.assertEqual(s['status'],'abandoned')
    def test_expired_reconnect(self):
        self.join_all();service.mutate(self.code,'p0','start')
        s=Room.objects.get(code=self.code).state
        s.update(paused=True,paused_at=time.time()-100);s['players'][0].update(connected=False,disconnected_at=time.time()-100)
        e.tick(s);self.assertEqual(s['status'],'abandoned')
    def test_csrf_and_endpoints(self):
        c=Client(enforce_csrf_checks=True);c.get('/')
        self.assertEqual(c.post('/api/create/',data='{}',content_type='application/json').status_code,403)
        response=c.post('/api/create/',data='{"name":"Alice","mode":"standard"}',content_type='application/json',HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value)
        self.assertEqual(response.status_code,200)

class PracticeTests(TestCase):
    def test_solo_full_match_and_rematch(self):
        code,state=service.create('solo','Solo','quick',practice=True)
        self.assertEqual(state['status'],'playing')
        self.assertEqual(sum(bool(p.get('bot')) for p in state['players']),3)
        self.assertEqual(len(state['hand']),13)
        self.assertNotIn('hands',state)
        now=time.time()
        for i in range(1500):
            with patch('game.service.time.time',return_value=now+i*2):
                if state['status']=='match_results': break
                if state['status']=='deal_results': state=service.mutate(code,'solo','next')
                elif state['status']=='chase_decision' and state['decision']['seat']==0: state=service.mutate(code,'solo','chase')
                elif state['legal']: state=service.mutate(code,'solo','play',{'card':state['legal'][0]})
                else: state=service.mutate(code,'solo','resync')
        self.assertEqual(state['status'],'match_results')
        state=service.mutate(code,'solo','rematch')
        self.assertEqual(state['status'],'playing')
        self.assertEqual(state['scores'],[0,0])
        state=service.mutate(code,'solo','quit')
        state=service.mutate(code,'solo','lobby')
        self.assertTrue(all(p['ready'] for p in state['players'] if p.get('bot')))

    def test_fill_empty_seats_requires_host_and_preserves_humans(self):
        code,_=service.create('host','Host','quick')
        service.mutate(code,'friend','join',{'name':'Friend'})
        with self.assertRaises(ValueError): service.mutate(code,'friend','bots')
        s=service.mutate(code,'host','bots')
        self.assertEqual(s['players'][1]['name'],'Friend')
        self.assertEqual(sum(bool(p.get('bot')) for p in s['players']),2)
