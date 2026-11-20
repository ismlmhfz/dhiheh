import copy, json, time, uuid
from django.test import TestCase, Client
from . import dutch_service as d, service
from .models import Room


class DutchServiceTests(TestCase):
    def setUp(self):
        self.state = d.create('a', 'Alice', 2); self.code = self.state['code']
        d.mutate(self.code, 'b', 'join', {'name': 'Bob'})
        for who in ['a', 'b']:
            d.mutate(self.code, who, 'connect', channel=who)
            self.action(who, 'ready')

    def action(self, who, action, **data):
        return d.mutate(self.code, who, action, {'command': str(uuid.uuid4()), **data})

    def begin(self, reveal=0):
        """Drive lobby -> playing. reveal=0 skips the starting peek, turn = chooser (seat 0)."""
        self.action('a', 'start')
        return self.action('a', 'choose_reveal', count=reveal)

    def test_host_controls_and_dedup(self):
        with self.assertRaises(ValueError): self.action('b', 'start')
        with self.assertRaises(ValueError): self.action('outsider', 'ready')
        cmd = {'command': str(uuid.uuid4())}
        first = d.mutate(self.code, 'a', 'ready', cmd); second = d.mutate(self.code, 'a', 'ready', cmd)
        self.assertEqual(first['players'][0]['ready'], second['players'][0]['ready'])

    def test_start_enters_choose_reveal(self):
        s = self.action('a', 'start')
        self.assertEqual(s['status'], 'choose_reveal')
        self.assertEqual(s['chooser'], 0)
        with self.assertRaises(ValueError):  # only the chooser picks
            self.action('b', 'choose_reveal', count=2)
        s = self.action('a', 'choose_reveal', count=0)
        self.assertEqual(s['status'], 'playing')
        self.assertEqual(s['turn'], 0)

    def test_duplicate_draw_and_preview_expiry_on_resync(self):
        s = self.begin(); now = time.time()
        who = ['a', 'b'][s['turn']]
        cmd = {'command': str(uuid.uuid4()), 'turn_id': s['turn_id']}
        first = d.mutate(self.code, who, 'draw', cmd, now=now)
        second = d.mutate(self.code, who, 'draw', cmd, now=now + 1)   # idempotent replay
        self.assertEqual(first['draw_count'], second['draw_count'])
        # 3s private preview: face hidden on resync after it expires, never shown to others
        self.assertIsNone(d.mutate(self.code, who, 'resync', now=now + 4)['drawn']['face'])
        self.assertIsNone(d.mutate(self.code, 'outsider', 'resync', now=now + 1)['drawn'])

    def test_no_pause_on_disconnect(self):
        s = self.begin(); now = time.time()
        d.mutate(self.code, 'a', 'disconnect', channel='a', now=now)
        resync = d.mutate(self.code, 'b', 'resync', now=now + 1)
        self.assertNotIn('paused', resync)          # no pausing in the new rules
        self.assertEqual(resync['status'], 'playing')
        self.assertFalse(resync['players'][0]['connected'])

    def test_all_idle_abandons_round(self):
        self.begin(); now = time.time()
        d.mutate(self.code, 'a', 'disconnect', channel='a', now=now)
        d.mutate(self.code, 'b', 'disconnect', channel='b', now=now)
        # still fine shortly after
        self.assertEqual(d.mutate(self.code, 'b', 'resync', now=now + 5)['status'], 'playing')
        # a full turn cycle with nobody connected -> abandoned
        self.assertEqual(d.mutate(self.code, 'b', 'resync', now=now + 40)['status'], 'abandoned')

    def test_multi_tab_disconnect_keeps_playing(self):
        self.begin()
        d.mutate(self.code, 'a', 'connect', channel='a2')
        d.mutate(self.code, 'a', 'disconnect', channel='a')
        s = d.mutate(self.code, 'a', 'resync')
        self.assertEqual(s['status'], 'playing')
        self.assertTrue(s['players'][0]['connected'])

    def test_long_absence_abandons_on_return(self):
        self.begin(); now = time.time()
        s = d.mutate(self.code, 'a', 'connect', channel='returned', now=now + 120)
        self.assertEqual(s['status'], 'abandoned')

    def test_safe_chat_and_nonmember_denial(self):
        with self.assertRaises(ValueError): d.chat_history(self.code, 'outsider')
        cmd = str(uuid.uuid4())
        a = d.chat_post(self.code, 'a', 'Hello', cmd); b = d.chat_post(self.code, 'a', 'Hello', cmd)
        self.assertEqual(a['id'], b['id']); self.assertEqual(len(d.chat_history(self.code, 'b')), 1)

    def test_ten_rooms_rejected_and_ten_routes_do_not_mutate_dutch(self):
        code, _ = service.create('ten', 'Ten', 'quick')
        with self.assertRaises(ValueError): d.mutate(code, 'ten', 'resync')
        for route in [f'/room/{self.code}/', f'/watch/{self.code}/', f'/spectate/api/{self.code}/']:
            self.assertEqual(self.client.get(route).status_code, 404)
        before = copy.deepcopy(Room.objects.get(code=self.code).state)
        response = self.client.post('/api/join/', json.dumps({'code': self.code, 'name': 'Attack'}), content_type='application/json')
        self.assertEqual(response.status_code, 404); self.assertEqual(Room.objects.get(code=self.code).state, before)
        self.assertEqual(self.client.get('/dutch/room/' + code + '/').status_code, 404)

    def test_csrf_and_safe_public_api(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post('/dutch/api/create/', json.dumps({'name': 'X', 'limit': 2}), content_type='application/json').status_code, 403)
        view = self.client.post('/dutch/api/resync/', json.dumps({'code': self.code}), content_type='application/json').json()
        self.assertIsNone(view['seat'])
        for p in view['players']:
            self.assertNotIn('id', p)

    def test_invalid_cut_rolls_back(self):
        self.begin(); before = Room.objects.get(code=self.code).state
        with self.assertRaises(ValueError):
            self.action('a', 'cut', event_id='wrong', slot='fake')
        self.assertEqual(before, Room.objects.get(code=self.code).state)

    def test_projection_hides_other_hands(self):
        s = self.begin()
        view = d.mutate(self.code, 'b', 'resync')
        self.assertTrue(all(c['face'] is None for c in view['hands'][0]))  # opponent hidden
        self.assertNotIn('cards', view)
        self.assertNotIn('draw_pile', view)

    def test_next_round_cannot_bypass_start(self):
        with self.assertRaises(ValueError): self.action('a', 'next_round')
        self.assertEqual(d.mutate(self.code, 'a', 'resync')['status'], 'lobby')

    def test_watch_projection_even_for_a_seated_session(self):
        session = self.client.session; session['player_id'] = 'a'; session.save()
        response = self.client.post('/dutch/api/resync/', json.dumps({'code': self.code, 'watch': True}), content_type='application/json')
        self.assertIsNone(response.json()['seat'])

    def test_poll_fallback_refreshes_only_own_presence(self):
        session = self.client.session; session['player_id'] = 'a'; session.save()
        s = self.client.post('/dutch/api/poll/', json.dumps({'code': self.code}), content_type='application/json').json()
        self.assertTrue(s['players'][0]['connected'])
        self.assertIn('http:a', Room.objects.get(code=self.code).state['players'][0]['connections'])

    def test_invites_expire_but_existing_seats_reconnect(self):
        room = Room.objects.get(code=self.code)
        room.state['players'][1] = None; room.state['invitation_closed'] = False
        room.state['created_at'] = time.time() - 3601; room.save()
        with self.assertRaises(ValueError): d.mutate(self.code, 'new', 'join', {'name': 'Late'})
        self.assertEqual(d.mutate(self.code, 'a', 'join', {'name': 'Original'})['seat'], 0)

    def test_rematch_resets_scores(self):
        self.begin()
        room = Room.objects.get(code=self.code)
        room.state.update(status='match_results', round=10, scores=[12, 7]); room.save()
        s = self.action('a', 'rematch')
        self.assertEqual(s['status'], 'lobby')
        self.assertEqual(s['scores'], [0, 0])
        self.assertEqual(s['round'], 0)
