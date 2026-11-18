"""Exercise real Channels consumers with separate viewer identities."""
import asyncio
import json
import time
import uuid
from django.test import TransactionTestCase
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from . import dutch_service as d
from .dutch_consumer import DutchConsumer, IsolatedTenConsumer
from .models import Room

class Session(dict):
    session_key='fallback'

class DutchSocketTests(TransactionTestCase):
    async def setup_table(self):
        def setup():
            s=d.create('alice','Alice',2);code=s['code']
            d.mutate(code,'bob','join',{'name':'Bob'})
            return code
        return await database_sync_to_async(setup)()
    async def socket(self,code,who,watch=False,consumer=DutchConsumer):
        c=WebsocketCommunicator(consumer.as_asgi(),'/')
        c.scope.update(session=Session(player_id=who),url_route={'kwargs':{'code':code,'watch':watch}})
        return c,await c.connect()
    async def receive(self,c,kind,predicate=lambda m:True):
        for _ in range(60):
            m=await c.receive_json_from(timeout=3)
            if m['type']==kind and predicate(m):return m
        self.fail('Expected message '+kind)
    async def send(self,c,action,**data):
        command=str(uuid.uuid4());await c.send_json_to({'action':'dutch.'+action,'command':command,**data})
        return (await self.receive(c,'dutch.ack',lambda m:m['command']==command))['state']
    async def test_views_private_timers_chat_and_reconnect(self):
        code=await self.setup_table();a,_=await self.socket(code,'alice');b,_=await self.socket(code,'bob');w,_=await self.socket(code,'alice',True)
        try:
            await self.send(a,'ready');await self.send(b,'ready');s=await self.send(a,'start')
            s=await self.send(a,'initial_peek',slots=s['slots'][:s['peek_count']]);self.assertTrue(s['reveals'])
            for c in [b,w]:
                m=await self.receive(c,'dutch.state',lambda m:m['state']['status']=='initial_peek')
                self.assertEqual(m['state']['reveals'],{});self.assertIsNone(m['state']['drawn'])
                for key in ['cards','hands','draw_pile','commands']:self.assertNotIn(key,m['state'])
            spec=(await self.receive(w,'dutch.state'))['state'];self.assertIsNone(spec['seat']);self.assertEqual(spec['slots'],[])
            await w.send_json_to({'action':'dutch.draw','command':str(uuid.uuid4())});await self.receive(w,'dutch.error')
            cmd=str(uuid.uuid4());await a.send_json_to({'action':'chat.send','command':cmd,'text':'Hello <script>'})
            await self.receive(a,'chat.sent');m=await self.receive(b,'chat.message');self.assertEqual(m['message']['text'],'Hello <script>')
            await asyncio.sleep(3.1);await a.disconnect();a,_=await self.socket(code,'alice')
            s=(await self.receive(a,'dutch.state'))['state'];self.assertEqual(s['reveals'],{});self.assertTrue(s['initial_selected'])
        finally:
            await a.disconnect();await b.disconnect();await w.disconnect()
    async def test_nonmembers_and_cross_game_socket_rejected(self):
        code=await self.setup_table()
        c,result=await self.socket(code,'outsider');self.assertFalse(result[0]);await c.disconnect()
        c,result=await self.socket(code,'alice',consumer=IsolatedTenConsumer);self.assertFalse(result[0]);await c.disconnect()
