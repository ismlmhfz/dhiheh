import copy, random
from unittest import TestCase
from . import dutch_engine as e

class DutchEngineTests(TestCase):
    def game(self,n=3,overrides=None):
        s=e.new_state(n,'host','Host',0,overrides)
        for i in range(n): s['players'][i]={'id':str(i),'name':str(i),'ready':True,'connected':True}
        e.start(s,0,0,random.Random(3))
        for i in range(n): e.act(s,i,'initial_peek',{'slots':[x['slot'] for x in s['hands'][i]][:s['peek_counts'][i]]},0)
        e.tick(s,4)
        return s

    def command(self,s,seat,action,now=5,**kw):
        return e.act(s,seat,action,{'turn_id':s['turn_id'],**kw},now)

    def conserved(self,s):
        ids=[x['card'] for h in s['hands'] for x in h]+s['draw_pile']+s['discard_pile']
        if s['reserved']:ids.append(s['reserved']['card'])
        self.assertEqual(len(ids),52);self.assertEqual(len(set(ids)),52)

    def test_deals_all_capacities_and_private_peeks(self):
        for n in range(2,7):
            s=e.new_state(n,'a','A',0)
            for i in range(n): s['players'][i]={'id':str(i),'name':str(i),'ready':True,'connected':True}
            e.start(s,0,0,random.Random(n));self.conserved(s)
            self.assertEqual([len(h) for h in s['hands']],[4]*n)
            self.assertEqual(len(s['draw_pile']),51-4*n)
            slots=[x['slot'] for x in s['hands'][0]][:s['peek_counts'][0]]
            e.act(s,0,'initial_peek',{'slots':slots},1)
            self.assertEqual(len(e.public(s,0,1)['reveals']),len(slots))
            for viewer in [1,None]:self.assertEqual(e.public(s,viewer,1)['reveals'],{})
            self.assertEqual(e.public(s,0,4)['reveals'],{})
            with self.assertRaises(ValueError):e.act(s,0,'initial_peek',{'slots':slots},5)

    def test_draw_hides_after_two_seconds_and_swap_conserves(self):
        s=self.game();seat=s['turn'];self.command(s,seat,'draw',10)
        self.assertIsNotNone(e.public(s,seat,11.99)['drawn']['face'])
        self.assertIsNone(e.public(s,seat,12)['drawn']['face'])
        self.assertIsNone(e.public(s,(seat+1)%3,11)['drawn'])
        self.command(s,seat,'swap_drawn',13,slot=s['hands'][seat][0]['slot']);self.conserved(s)

    def test_wrong_turn_and_first_cycle_locks(self):
        s=self.game();seat=(s['turn']+1)%3
        for action in ['draw','call']:
            with self.assertRaises(ValueError):self.command(s,seat,action)
        with self.assertRaises(ValueError):self.command(s,s['turn'],'call')
        with self.assertRaises(ValueError):self.command(s,seat,'cut',slots=[s['hands'][seat][0]['slot']],event_id='fake')

    def test_ten_rounds_and_final_turns(self):
        for n in [2,3,5,6]:
            s=self.game(n)
            for rnd in range(1,11):
                now=rnd*100
                for _ in range(n):
                    seat=s['turn'];self.command(s,seat,'take_discard',now,slot=s['hands'][seat][0]['slot']);now+=15;e.tick(s,now)
                caller=s['turn'];self.command(s,caller,'call',now)
                order=s['final_turn_order'][:];self.assertEqual(len(set(order)),n-1);self.assertNotIn(caller,order)
                for seat in order:
                    with self.assertRaises(ValueError):self.command(s,seat,'cut',now,slots=[s['hands'][seat][0]['slot']],event_id='fake')
                    self.command(s,seat,'take_discard',now,slot=s['hands'][seat][0]['slot']);now+=15;e.tick(s,now)
                self.assertEqual(len(s['round_history']),rnd);self.conserved(s)
                if rnd<10:
                    e.next_round(s,now,random.Random(rnd));e.tick(s,now+40)
                else:self.assertEqual(s['status'],'match_results');self.assertTrue(s['winner_seats'])

    def test_stale_turn(self):
        s=self.game();seat=s['turn'];old=s['turn_id'];self.command(s,seat,'draw')
        with self.assertRaises(ValueError):e.act(s,seat,'swap_drawn',{'turn_id':old,'slot':s['hands'][seat][0]['slot']},6)

    def test_public_allowlist(self):
        s=self.game(6)
        for viewer in [None,*range(6)]:
            view=e.public(s,viewer,10)
            for key in ['cards','hands','draw_pile','discard_pile','commands','reserved','initial_peeks','jack_peeks']:self.assertNotIn(key,view)
            self.assertFalse(any('id' in p or 'connections' in p for p in view['players']))
            self.assertEqual(len(view['slots']),0 if viewer is None else 4)

    def layout(self,s,hands,top):
        remaining=list(s['cards'])
        def get(face):
            cid=next(c for c in remaining if s['cards'][c]['rank']+s['cards'][c]['suit']==face);remaining.remove(cid);return cid
        s['hands']=[[{'slot':f'slot-{i}-{j}','card':get(c)} for j,c in enumerate(h)] for i,h in enumerate(hands)]
        s['discard_pile']=[get(top)];s['draw_pile']=remaining;s['reserved']=None;s['jack_peeks']={}
        s['first_turn_done']=[True]*len(hands);s['status']='playing';s['phase']='normal_choice'
        return s

    def test_multi_cut_rank_and_stale_race(self):
        s=self.layout(self.game(),[['2C','2D','2H','AC'],['3C'],['4C']],'2S');e.open_cut(s,5);old=s['cut_window']['event_id']
        self.command(s,0,'cut',6,slots=[x['slot'] for x in s['hands'][0]][:3],event_id=old)
        self.assertEqual(len(s['hands'][0]),1);self.assertEqual(s['turn'],0);self.conserved(s)
        before=copy.deepcopy(s)
        with self.assertRaises(ValueError):self.command(s,1,'cut',6,slots=[s['hands'][1][0]['slot']],event_id=old)
        self.assertEqual(s,before)

    def test_bad_batch_single_unseen_penalty_and_turn(self):
        s=self.layout(self.game(),[['2C','3C'],['4C'],['5C']],'2S');e.open_cut(s,5)
        self.command(s,0,'cut',6,slots=[x['slot'] for x in s['hands'][0]],event_id=s['cut_window']['event_id'])
        self.assertEqual(len(s['hands'][0]),3);self.assertEqual(s['turn'],0);self.assertEqual(e.public(s,0,6)['reveals'],{});self.conserved(s)

    def test_last_jack_cut_ends_round_before_peek(self):
        s=self.layout(self.game(),[['JC','JD'],['4C'],['5C']],'JS');e.open_cut(s,5)
        self.command(s,0,'cut',6,slots=[x['slot'] for x in s['hands'][0]],event_id=s['cut_window']['event_id'])
        self.assertEqual(s['status'],'round_results');self.assertEqual(s['scores'],[0,4,5]);self.assertFalse(s['jack_peeks']);self.assertIsNone(s['turn'])
        self.assertEqual(s['final_turn_order'],[]);self.conserved(s)

    def test_jack_one_second_private_and_not_replayable(self):
        s=self.layout(self.game(),[['JC','3C'],['4C'],['5C']],'AS');s['turn']=0
        self.command(s,0,'take_discard',5,slot=s['hands'][0][0]['slot'])
        turn=s['turn'];handle=s['hands'][0][1]['slot']
        self.command(s,0,'jack_peek',6,slot=handle)
        self.assertIn(handle,e.public(s,0,6.99)['reveals']);self.assertEqual(e.public(s,1,6.5)['reveals'],{})
        self.assertEqual(e.public(s,0,7)['reveals'],{});self.assertEqual(turn,s['turn'])
        with self.assertRaises(ValueError):self.command(s,0,'jack_peek',6.5,slot=handle)

    def test_scores_failed_successful_and_ties(self):
        for hands,expected in [([['7C'],['9C'],['QC'],['KC','3C']],[7,18,12,16]),([['7C'],['5C'],['QC'],['KC','3C']],[7,0,12,16]),([['5D'],['5C'],['QC'],['KC','3C']],[5,0,12,16])]:
            s=self.layout(self.game(4),hands,'AS');s['status']='dutch_final';e.finish(s,'dutch',1)
            self.assertEqual(s['scores'],expected)
            old=copy.deepcopy(s)
            with self.assertRaises(ValueError):e.finish(s,'dutch',1)
            self.assertEqual(old,s)
        s=self.layout(self.game(2,{'dutch_ties_win':False}),[['5D'],['5C']],'AS');s['status']='dutch_final';e.finish(s,'dutch',1);self.assertEqual(s['scores'],[5,10])

    def test_recycle_and_unavailable_penalty_no_phantom_card(self):
        s=self.game();s['discard_pile']=s['draw_pile']+s['discard_pile'];s['draw_pile']=[]
        top=s['discard_pile'][-1];card=e.draw_card(s,random.Random(1));self.assertEqual(s['discard_pile'],[top]);s['draw_pile'].append(card);self.conserved(s)
        s=self.layout(self.game(2),[['2C'],['3C']],'AS');s['hands'][1].extend({'slot':str(i),'card':c} for i,c in enumerate(s['draw_pile']));s['draw_pile']=[]
        e.open_cut(s,5);old=copy.deepcopy(s)
        with self.assertRaises(ValueError):self.command(s,0,'cut',6,slots=['slot-0-0'],event_id=s['cut_window']['event_id'])
        self.assertEqual(s,old);self.conserved(s)

    def test_seeded_random_legal_play_conserves_cards(self):
        for n in range(2,7):
            rng=random.Random(n);s=self.game(n);now=20
            for _ in range(160):
                now+=15;e.tick(s,now)
                if s['status'] in e.RESULTS:break
                seat=s['turn'];handle=rng.choice(s['hands'][seat])['slot']
                if s['cut_window']:continue
                if all(s['first_turn_done']) and not s['jack_peeks'] and rng.random()<.08:self.command(s,seat,'call',now)
                elif rng.random()<.5 and (s['draw_pile'] or len(s['discard_pile'])>1):
                    self.command(s,seat,'draw',now);self.command(s,seat,'swap_drawn',now+3,slot=handle)
                else:self.command(s,seat,'take_discard',now,slot=handle)
                self.conserved(s)

    def test_configuration_changes_are_frozen_and_honored(self):
        s=self.game(2,{'direction':-1,'peek_min':2,'peek_max':2,'initial_peek_seconds':1})
        self.assertEqual(s['peek_counts'],[2,2]);self.assertEqual(e.next_seat(s,0),1)
        self.assertEqual(s['rules']['initial_peek_seconds'],1)

    def test_final_swap_can_overtake_caller_and_rejects_second_call(self):
        s=self.layout(self.game(2),[['5C'],['9C']],'AC');s['turn']=0
        self.command(s,0,'call',5)
        with self.assertRaises(ValueError):self.command(s,1,'call',6)
        self.command(s,1,'take_discard',6,slot=s['hands'][1][0]['slot'])
        self.assertEqual(s['scores'],[10,1]);self.assertFalse(s['round_result']['success'])

    def test_match_tie_and_no_eleventh_round(self):
        s=self.layout(self.game(2),[['5C'],['5D']],'AC');s['round']=10;s['scores']=[5,0]
        e.finish(s,'dutch',0)
        self.assertEqual(s['scores'],[5,5]);self.assertEqual(s['winner_seats'],[0,1])
        with self.assertRaises(ValueError):e.next_round(s,10)

    def test_initial_timeout_and_foreign_slot(self):
        s=e.new_state(2,'a','A',0)
        for i in range(2):s['players'][i]={'id':str(i),'name':str(i),'ready':True,'connected':True}
        e.start(s,0,0,random.Random(4))
        with self.assertRaises(ValueError):self.command(s,0,'initial_peek',1,slots=[s['hands'][1][0]['slot']])
        e.tick(s,31);self.assertEqual(s['status'],'playing');self.assertTrue(all(s['initial_peeks_done']))
        self.assertEqual(e.public(s,0,31)['reveals'],{})
