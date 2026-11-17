from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from . import service, chat
from .models import ChatMessage

class ChatTests(TestCase):
    def setUp(self):
        self.code,_=service.create('host','Host','quick')
        service.mutate(self.code,'guest','join',{'name':'Guest'})
    def test_shared_history_and_no_private_identity(self):
        m=chat.post(self.code,'host',' Hello <b>team</b> ','one')
        self.assertEqual(m['text'],'Hello <b>team</b>')
        self.assertEqual(chat.history(self.code,'guest')[0]['id'],m['id'])
        self.assertEqual(m['seat'],0)
        self.assertNotIn('sender',m)
    def test_nonmember_and_cross_room_access(self):
        other,_=service.create('outsider','Other','quick')
        with self.assertRaises(ValueError): chat.history(self.code,'outsider')
        with self.assertRaises(ValueError): chat.post(self.code,'outsider','Hi','one')
        chat.post(self.code,'host','Private','one')
        self.assertEqual(chat.history(other,'outsider'),[])
    def test_validation_rate_limit_and_duplicate(self):
        for text in ['', '   ', 'a'*121, None, {}]:
            with self.assertRaises(ValueError): chat.post(self.code,'host',text,'bad')
        first=chat.post(self.code,'host','hello','one')
        self.assertEqual(chat.post(self.code,'host','hello','one'),first)
        for i in range(4): chat.post(self.code,'host','hello',str(i))
        with self.assertRaises(ValueError): chat.post(self.code,'host','too fast','six')
    def test_keeps_last_100_messages(self):
        for i in range(105):
            ChatMessage.objects.filter(room__code=self.code).update(created_at=timezone.now()-timedelta(seconds=20))
            chat.post(self.code,'host',str(i),str(i))
        history=chat.history(self.code,'guest')
        self.assertEqual(len(history),100)
        self.assertEqual(history[0]['text'],'5')
