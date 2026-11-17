from django.test import TestCase
from . import service
from .models import Room

class TeamSelectionTests(TestCase):
    def setUp(self):
        self.code,_=service.create('p0','Host','quick')
        for i in range(1,4): service.mutate(self.code,f'p{i}','join',{'name':f'P{i}'})
    def ready_all(self):
        for i in range(4): service.mutate(self.code,f'p{i}','ready')
    def test_unbalanced_teams_block_start_even_when_all_ready(self):
        service.mutate(self.code,'p1','team',{'team':0})
        self.ready_all()
        with self.assertRaisesMessage(ValueError,'exactly two'): service.mutate(self.code,'p0','start')
    def test_switching_full_teams_and_arranging_opposite_seats(self):
        self.ready_all()
        service.mutate(self.code,'p0','team',{'team':1})
        s=Room.objects.get(code=self.code).state
        self.assertTrue(all(not p['ready'] for p in s['players']))
        service.mutate(self.code,'p1','team',{'team':0})
        self.ready_all()
        s=service.mutate(self.code,'p0','start')
        self.assertEqual(s['status'],'playing')
        self.assertEqual(s['host'],s['seat'])
        private=Room.objects.get(code=self.code).state
        self.assertEqual([p['team'] for p in private['players']],[0,1,0,1])
        self.assertEqual({p['id'] for p in private['players']},{f'p{i}' for i in range(4)})
        self.assertEqual([len(h) for h in private['hands']],[13]*4)
        self.assertEqual(service.mutate(self.code,'p0','resync')['seat'],s['seat'])
        with self.assertRaisesMessage(ValueError,'after the match'): service.mutate(self.code,'p0','team',{'team':0})
    def test_invalid_choices_and_noop_preserves_ready(self):
        self.ready_all()
        service.mutate(self.code,'p0','team',{'team':0})
        self.assertTrue(Room.objects.get(code=self.code).state['players'][0]['ready'])
        for value in (True,-1,2,'0',None):
            with self.assertRaises(ValueError): service.mutate(self.code,'p0','team',{'team':value})

    def test_team_names_are_own_team_only_and_persist(self):
        service.mutate(self.code,'p0','team_name',{'name':'Night Owls','team':1})
        state=service.mutate(self.code,'p1','resync')
        self.assertEqual(state['team_names'],['Night Owls','Amber'])
        service.mutate(self.code,'p2','team_name',{'name':'Star Players'})
        self.ready_all()
        state=service.mutate(self.code,'p0','start')
        self.assertEqual(state['team_names'],['Star Players','Amber'])
        with self.assertRaisesMessage(ValueError,'locked'):
            service.mutate(self.code,'p1','team_name',{'name':'Comets'})
        self.assertEqual(service.mutate(self.code,'p0','resync')['team_names'],['Star Players','Amber'])
    def test_team_name_validation(self):
        for name in ['', '  ', None, 'x'*19, 'amber']:
            with self.assertRaises(ValueError):
                service.mutate(self.code,'p0','team_name',{'name':name})
