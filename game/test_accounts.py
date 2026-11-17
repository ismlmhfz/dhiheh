from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core import mail
from .models import Profile
from . import service
from unittest.mock import AsyncMock, patch
from django.test import SimpleTestCase
from .consumer import RoomConsumer

class AccountTests(TestCase):
    def test_signup_profile_and_guest_seat_survives_login(self):
        self.client.get('/')
        response=self.client.post('/api/create/',data={'name':'Guest','mode':'quick'},content_type='application/json')
        code=response.json()['code']
        original_identity=self.client.session['player_id']
        response=self.client.post('/signup/',{'username':'newplayer','email':'player@example.com','password1':'MyFunCardParty567!','password2':'MyFunCardParty567!'})
        self.assertRedirects(response,'/profile/')
        self.assertEqual(self.client.session['player_id'],original_identity)
        self.assertEqual(self.client.post('/api/resync/',{'code':code},content_type='application/json').json()['state']['seat'],0)
        response=self.client.post('/profile/',{'nickname':'Sunny','avatar':'frog','deck':'candy'})
        self.assertContains(response,'Profile saved')
        self.assertEqual(Profile.objects.get(user__username='newplayer').avatar,'frog')
        self.client.post('/logout/')
        response=self.client.post('/login/',{'username':'newplayer','password':'MyFunCardParty567!'})
        self.assertRedirects(response,'/')

    def test_profile_preferences_and_authentication(self):
        user=User.objects.create_user('saved',password='MyFunCardParty567!')
        self.assertEqual(self.client.post('/api/preferences/',{'avatar':'fox'},content_type='application/json').status_code,403)
        self.client.force_login(user)
        response=self.client.post('/api/preferences/',{'avatar':'dragon','deck':'lagoon'},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(Profile.objects.get(user=user).deck,'lagoon')
        self.assertEqual(self.client.post('/api/preferences/',{'avatar':'<script>'},content_type='application/json').status_code,400)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_and_no_account_disclosure(self):
        User.objects.create_user('reset',email='reset@example.com',password='MyFunCardParty567!')
        for email in ['reset@example.com','unknown@example.com']:
            self.assertRedirects(self.client.post('/password-reset/',{'email':email}),'/password-reset/sent/')
        self.assertEqual(len(mail.outbox),1)
        self.assertIn('/reset/',mail.outbox[0].body)

    def test_voice_presence_and_owner_private(self):
        code,_=service.create('a','Alice','quick')
        service.mutate(code,'b','join',{'name':'Bob'})
        state=service.mutate(code,'a','voice_join',{'owner':'channel-a'})
        self.assertTrue(state['players'][0]['voice'])
        self.assertNotIn('voice_owner',state['players'][0])
        state=service.mutate(code,'a','voice_mute',{'owner':'channel-a','muted':True})
        self.assertTrue(state['players'][0]['voice_muted'])
        state=service.mutate(code,'a','voice_leave',{'owner':'old-channel'})
        self.assertTrue(state['players'][0]['voice'])
        state=service.mutate(code,'a','voice_leave',{'owner':'channel-a'})
        self.assertFalse(state['players'][0]['voice'])
        with self.assertRaises(ValueError): service.mutate(code,'outsider','voice_join',{'owner':'x'})

class VoiceDisconnectTests(SimpleTestCase):
    async def test_departure_is_broadcast_after_lobby_seat_removed(self):
        consumer=RoomConsumer()
        consumer.voice=True;consumer.voice_session='session';consumer.code='TEST12';consumer.identity='guest'
        consumer.channel_name='voice-channel';consumer.seat=2
        consumer.channel_layer=AsyncMock()
        with patch('game.consumer.database_sync_to_async',return_value=AsyncMock(side_effect=ValueError('Join this room first.'))):
            await consumer.leave_voice()
        self.assertFalse(consumer.voice)
        consumer.channel_layer.group_send.assert_awaited_once_with('room_TEST12',{'type':'voice_event','payload':{'type':'voice.left','seat':2,'session':'session'}})
