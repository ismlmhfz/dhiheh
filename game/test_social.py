from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from .models import Friendship, Conversation, ConversationMember, ConversationMessage, GroupMatch, Room
from . import service
from .spectator import snapshot

User=get_user_model()

class SocialTests(TestCase):
    def setUp(self):
        self.users=[User.objects.create_user(f'player{i}',password='Test-only-password-789!') for i in range(5)]
        self.clients=[]
        for user in self.users:
            c=Client();c.force_login(user);c.get('/');self.clients.append(c)
    def post(self,i,action,**data):
        return self.clients[i].post('/social/api/action/'+action+'/',data,content_type='application/json')
    def friend(self,a,b):
        response=self.post(a,'friend_request',username=self.users[b].username)
        self.assertEqual(response.status_code,200)
        f=Friendship.objects.get(first_id=min(self.users[a].id,self.users[b].id),second_id=max(self.users[a].id,self.users[b].id))
        self.assertEqual(self.post(b,'friend_accept',id=f.id).status_code,200)
        return f
    def group(self):
        for i in range(1,4):self.friend(0,i)
        response=self.post(0,'group_create',title='Game night',user_ids=[u.id for u in self.users[1:4]])
        self.assertEqual(response.status_code,200,response.content)
        return response.json()['id']
    def test_login_and_friend_acceptance(self):
        self.assertEqual(Client().get('/friends/').status_code,302)
        self.assertEqual(Client().get('/social/api/overview/').status_code,302)
        self.assertEqual(self.post(0,'friend_request',username='player0').status_code,400)
        self.assertEqual(self.post(0,'direct',user_id=self.users[1].id).status_code,400)
        self.post(0,'friend_request',username='player1')
        f=Friendship.objects.get()
        self.assertEqual(self.post(0,'friend_accept',id=f.id).status_code,400)
        self.assertEqual(self.post(2,'friend_accept',id=f.id).status_code,404)
        self.assertEqual(self.post(1,'friend_accept',id=f.id).status_code,200)
        data=self.clients[0].get('/social/api/overview/').json()
        self.assertEqual(data['friends'][0]['person']['username'],'player1')
        self.assertNotIn('email',data['friends'][0]['person'])
    def test_private_chat_membership_idempotence_and_unread(self):
        self.friend(0,1)
        cid=self.post(0,'direct',user_id=self.users[1].id).json()['id']
        self.assertEqual(self.post(1,'direct',user_id=self.users[0].id).json()['id'],cid)
        for _ in range(2):self.assertEqual(self.post(0,'send',conversation_id=cid,text='Hello <script>',command='one').status_code,200)
        self.assertEqual(ConversationMessage.objects.count(),1)
        self.assertEqual(self.clients[2].get(f'/social/api/conversation/{cid}/').status_code,404)
        self.assertEqual(self.post(2,'send',conversation_id=cid,text='Intruder',command='two').status_code,404)
        data=self.clients[1].get(f'/social/api/conversation/{cid}/').json()
        self.assertEqual(data['messages'][0]['text'],'Hello <script>')
        self.assertEqual(data['conversation']['unread'],1)
        self.post(1,'read',conversation_id=cid,message_id=data['messages'][0]['id'])
        self.assertEqual(self.clients[1].get(f'/social/api/conversation/{cid}/').json()['conversation']['unread'],0)
    def test_removed_friend_cannot_message(self):
        f=self.friend(0,1);cid=self.post(0,'direct',user_id=self.users[1].id).json()['id']
        self.post(0,'friend_remove',id=f.id)
        self.assertEqual(self.post(1,'send',conversation_id=cid,text='Hi',command='one').status_code,400)
    def test_group_creation_and_owner_permissions(self):
        self.assertEqual(self.post(0,'group_create',title='No consent',user_ids=[self.users[4].id]).status_code,400)
        cid=self.group()
        self.assertEqual(self.clients[4].get(f'/social/api/conversation/{cid}/').status_code,404)
        self.assertEqual(self.post(1,'group_rename',conversation_id=cid,title='Changed').status_code,400)
        self.assertEqual(self.post(0,'group_rename',conversation_id=cid,title='Our group').status_code,200)
        self.friend(0,4)
        self.assertEqual(self.post(1,'group_add',conversation_id=cid,user_id=self.users[4].id).status_code,400)
        self.assertEqual(self.post(0,'group_add',conversation_id=cid,user_id=self.users[4].id).status_code,200)
        self.assertEqual(self.clients[4].get(f'/social/api/conversation/{cid}/').status_code,200)
        self.assertEqual(self.post(4,'group_leave',conversation_id=cid).status_code,200)
        self.assertEqual(self.clients[4].get(f'/social/api/conversation/{cid}/').status_code,404)
    def test_group_match_invitation_and_public_watch(self):
        cid=self.group()
        response=self.post(0,'match_create',conversation_id=cid,mode='quick',command='match-one')
        self.assertEqual(response.status_code,200,response.content)
        code=response.json()['code']
        self.assertEqual(self.post(0,'match_create',conversation_id=cid,mode='quick',command='match-one').json()['code'],code)
        self.assertEqual(GroupMatch.objects.count(),1)
        self.assertEqual(self.post(1,'match_create',conversation_id=cid,command='match-two').status_code,400)
        self.assertEqual(self.post(4,'match_create',conversation_id=cid,command='bad').status_code,404)
        invite=self.clients[1].get(f'/social/api/conversation/{cid}/').json()['messages'][0]['match']
        self.assertEqual(invite['watch_url'],f'/watch/{code}/')
        self.assertEqual(self.clients[4].post('/api/join/',{'code':code,'name':'Intruder'},content_type='application/json').status_code,400)
        self.assertEqual(Client().get(f'/room/{code}/')['Location'],f'/watch/{code}/')
        self.assertEqual(Client().get(f'/watch/{code}/').status_code,200)
        self.assertFalse(Client().get(f'/spectate/api/{code}/').json()['can_join'])
        for i in range(1,4):
            self.assertEqual(self.clients[i].post('/api/join/',{'code':code,'name':f'Player {i}'},content_type='application/json').status_code,200)
        for i in range(4):self.clients[i].post('/api/ready/',{'code':code},content_type='application/json')
        response=self.clients[0].post('/api/start/',{'code':code},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['state']['status'],'playing')
        watch=Client().get(f'/spectate/api/{code}/').json()
        self.assertEqual(watch['state']['counts'],[13,13,13,13])
        self.assertNotIn('hand',watch['state']);self.assertNotIn('hands',watch['state'])
        self.assertNotIn('creator',watch['state']);self.assertNotIn('commands',watch['state'])
        for p in watch['state']['players']:
            for private in ['id','voice_owner','connections']:self.assertNotIn(private,p)
        self.assertIsNone(watch['group_id'])
        self.assertEqual(self.post(0,'group_leave',conversation_id=cid).status_code,400)
    def test_group_identity_survives_new_login_session(self):
        cid=self.group();code=self.post(0,'match_create',conversation_id=cid,command='one').json()['code']
        other=Client();other.force_login(self.users[0])
        response=other.post('/api/resync/',{'code':code},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['state']['seat'],0)
    def test_empty_group_lobby_can_be_replaced(self):
        cid=self.group();code=self.post(0,'match_create',conversation_id=cid,command='one').json()['code']
        self.clients[0].post('/api/leave/',{'code':code},content_type='application/json')
        response=self.post(0,'match_create',conversation_id=cid,command='two')
        self.assertEqual(response.status_code,200,response.content)
        self.assertNotEqual(response.json()['code'],code)
    def test_chat_validation_and_rate_limit(self):
        self.friend(0,1);cid=self.post(0,'direct',user_id=self.users[1].id).json()['id']
        for text in ['', ' ',None,'x'*1001]:self.assertEqual(self.post(0,'send',conversation_id=cid,text=text,command='bad').status_code,400)
        for i in range(30):self.assertEqual(self.post(0,'send',conversation_id=cid,text='Hello',command=str(i)).status_code,200)
        self.assertEqual(self.post(0,'send',conversation_id=cid,text='Stop',command='thirty-one').status_code,400)
    def test_spectator_does_not_mutate_room_or_expose_future_cards(self):
        code,_=service.create('secret-session','Host','quick',practice=True)
        room=Room.objects.get(code=code);before=room.state.copy()
        room.state['unexpected_secret']='do not expose';room.save()
        data=Client().get(f'/spectate/api/{code}/').json()['state']
        self.assertNotIn('unexpected_secret',data)
        self.assertNotIn('secret-session',str(data))
        self.assertEqual(data['trick'],[])
        self.assertEqual(data['counts'],[13,13,13,13])
        self.assertEqual(Client().post(f'/spectate/api/{code}/',{'action':'play'}).status_code,405)
        room.refresh_from_db();self.assertEqual(room.state['hands'],before['hands'])
    def test_csrf_required_for_social_mutations(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.users[0])
        self.assertEqual(client.post('/social/api/action/friend_request/',{'username':'player1'},content_type='application/json').status_code,403)
