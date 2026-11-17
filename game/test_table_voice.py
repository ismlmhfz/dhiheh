from django.test import TestCase, override_settings
from unittest.mock import patch
from . import service
from .models import Room
from .voice import configuration
import base64, hmac, hashlib

class TableVoiceTests(TestCase):
    def test_only_host_can_delete(self):
        code,_=service.create('host','Host','quick')
        service.mutate(code,'guest','join',{'name':'Guest'})
        for identity in ['guest','outsider']:
            with self.assertRaises(ValueError): service.delete_table(code,identity)
        self.assertTrue(Room.objects.filter(code=code).exists())
        service.delete_table(code,'host')
        self.assertFalse(Room.objects.filter(code=code).exists())

    def test_transferred_host_can_delete(self):
        code,_=service.create('host','Host','quick')
        service.mutate(code,'guest','join',{'name':'Guest'})
        service.mutate(code,'host','leave')
        service.delete_table(code,'guest')
        self.assertFalse(Room.objects.filter(code=code).exists())

    @override_settings(VOICE_ICE_SERVERS=[])
    @patch.dict('os.environ',{'TURN_SHARED_SECRET':'test-secret','TURN_RELAY_URLS':'turn:relay:3478'})
    @patch('game.voice.time.time',return_value=1000)
    def test_temporary_relay_credentials(self,clock):
        server=configuration('private-player-id')['iceServers'][0]
        self.assertTrue(server['username'].startswith('87400:'))
        self.assertNotIn('private-player-id',str(server))
        expected=base64.b64encode(hmac.new(b'test-secret',server['username'].encode(),hashlib.sha1).digest()).decode()
        self.assertEqual(server['credential'],expected)

    def test_voice_config_requires_seat(self):
        code,_=service.create('host','Host','quick')
        result=self.client.post('/api/voice_config/',{'code':code},content_type='application/json')
        self.assertEqual(result.status_code,400)

    def test_group_deletion_keeps_conversation(self):
        from django.contrib.auth import get_user_model
        from .models import Conversation, GroupMatch, ConversationMessage
        user=get_user_model().objects.create_user('delete-host')
        code,_=service.create(f'account:{user.pk}','Host','quick')
        conversation=Conversation.objects.create(kind='group',title='Friends',owner=user)
        match=GroupMatch.objects.create(room=Room.objects.get(code=code),conversation=conversation,created_by=user)
        message=ConversationMessage.objects.create(conversation=conversation,sender=user,text='Join my table',command='invite',match=match)
        service.delete_table(code,f'account:{user.pk}')
        message.refresh_from_db()
        self.assertIsNone(message.match_id)
        self.assertIn('deleted',message.text)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())
