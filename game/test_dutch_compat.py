"""Previously deployed rooms retain their frozen rules and projections."""
import json,uuid
from django.test import TestCase
from . import dutch_service as current,dutch_legacy_service as old
from .models import Room

class DutchCompatibilityTests(TestCase):
    def test_original_room_dispatch_and_template(self):
        code=old.create('old-a','Original',2)['code']
        current.mutate(code,'old-b','join',{'name':'Guest'})
        for who in ['old-a','old-b']:
            current.mutate(code,who,'connect',channel=who)
            current.mutate(code,who,'ready',{'command':str(uuid.uuid4())})
        state=current.mutate(code,'old-a','start',{'command':str(uuid.uuid4())})
        self.assertEqual(state['status'],'initial_peek')
        self.assertIn('peek_count',state);self.assertNotIn('hands',state)
        self.assertEqual(Room.objects.get(code=code).state['schema_version'],1)
        response=self.client.get('/dutch/room/'+code+'/')
        self.assertContains(response,'dutch/legacy.js')
        response=self.client.post('/dutch/api/resync/',json.dumps({'code':code}),content_type='application/json')
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['slots'],[])
    def test_new_tables_use_updated_rules(self):
        state=current.create('new-a','Updated',2)
        self.assertIn('hands',state);self.assertIn('turn_seconds',state['rules'])
        self.assertEqual(Room.objects.get(code=state['code']).state['schema_version'],2)
