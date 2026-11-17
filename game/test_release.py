from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from . import engine,service
from .models import Room,Conversation,GroupMatch,ConversationMessage,ConversationMember
from .invitations import details
from .social import message_data

class InvitationTests(TestCase):
    def setUp(self):self.code,_=service.create('host','Host','quick')
    def test_expired_link_blocks_join_but_not_reconnection(self):
        Room.objects.filter(code=self.code).update(created_at=timezone.now()-timedelta(hours=1,seconds=1))
        with self.assertRaisesMessage(ValueError,'expired'):service.mutate(self.code,'new','join',{'name':'New'})
        self.assertEqual(service.mutate(self.code,'host','join')['seat'],0)
        self.assertEqual(self.client.get('/room/'+self.code+'/').status_code,302)
        self.assertFalse(self.client.get('/spectate/api/'+self.code+'/').json()['can_join'])
        self.assertEqual(self.client.get('/watch/'+self.code+'/').status_code,200)
    def test_full_invitation_never_reopens_on_leave(self):
        for i in range(1,4):service.mutate(self.code,str(i),'join',{'name':str(i)})
        service.mutate(self.code,'3','leave')
        with self.assertRaisesMessage(ValueError,'closed'):service.mutate(self.code,'new','join',{'name':'New'})
        self.assertFalse(details(Room.objects.get(code=self.code))['open'])
    def test_group_card_expires_and_seated_player_can_open(self):
        user=get_user_model().objects.create_user('group-host')
        code,_=service.create(f'account:{user.pk}','Group host','quick')
        c=Conversation.objects.create(kind='group',title='Group',owner=user)
        ConversationMember.objects.create(conversation=c,user=user)
        match=GroupMatch.objects.create(room=Room.objects.get(code=code),conversation=c,created_by=user)
        m=ConversationMessage.objects.create(conversation=c,sender=user,command='test',match=match)
        Room.objects.filter(code=code).update(created_at=timezone.now()-timedelta(hours=2))
        m=ConversationMessage.objects.select_related('match__room').get(pk=m.pk)
        card=message_data(m,user)['match']
        self.assertFalse(card['invitation']['open']);self.assertTrue(card['seated'])
    def test_open_for_first_hour(self):
        self.assertTrue(details(Room.objects.get(code=self.code))['open'])
        service.mutate(self.code,'new','join',{'name':'New'})

class RandomOpeningTests(TestCase):
    def test_each_deal_draws_a_fresh_opening_seat(self):
        s={'players':[{}]*4,'mode':'standard','deal':0}
        with patch('game.engine.secrets.randbelow',side_effect=[2,0,3,1]) as random:
            for expected in [2,0,3,1]:
                engine.new_deal(s)
                self.assertEqual(s['starter'],expected);self.assertEqual(s['turn'],expected)
            self.assertEqual(random.call_count,4)

class AdminTests(TestCase):
    def test_access_control_and_pages(self):
        normal=get_user_model().objects.create_user('player')
        self.assertEqual(self.client.get('/admin/').status_code,302)
        self.client.force_login(normal)
        self.assertEqual(self.client.get('/admin/').status_code,302)
        admin=get_user_model().objects.create_superuser('operator','op@example.test','test-pass')
        self.client.force_login(admin)
        for url in ['/admin/','/admin/auth/user/','/admin/game/room/','/admin/game/conversation/','/admin/admin/logentry/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        code,_=service.create('private-id','Player','quick',practice=True)
        response=self.client.get(f'/admin/game/room/{Room.objects.get(code=code).pk}/change/')
        self.assertNotContains(response,'private-id');self.assertNotContains(response,'name="state"')
