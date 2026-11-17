from django.test import SimpleTestCase
from unittest.mock import AsyncMock, patch
from .consumer import RoomConsumer

class VoiceSessionTests(SimpleTestCase):
    def consumer(self):
        c=RoomConsumer();c.voice=True;c.voice_session='new';c.signal_times=[]
        c.code='TEST';c.identity='host';c.channel_name='host-channel';c.seat=0
        c.channel_layer=AsyncMock();c.send_json=AsyncMock()
        return c

    async def test_old_leave_cannot_disconnect_new_session(self):
        c=self.consumer()
        await c.voice_action('voice.leave',{'session':'old'})
        self.assertTrue(c.voice)
        c.channel_layer.group_send.assert_not_awaited()

    async def test_old_signal_cannot_enter_new_session(self):
        c=self.consumer()
        await c.voice_action('voice.signal',{'session':'old','target':1,'signal':{}})
        c.channel_layer.group_send.assert_not_awaited()

    async def test_signal_checks_recipient_session(self):
        c=self.consumer()
        state={'seat':0,'players':[{'voice':True,'voice_session':'new'},{'voice':True,'voice_session':'recipient-new'}]}
        mutate=AsyncMock(return_value=state)
        with patch('game.consumer.database_sync_to_async',return_value=mutate):
            await c.voice_action('voice.signal',{'session':'new','target':1,'target_session':'recipient-old','signal':{}})
            c.channel_layer.group_send.assert_not_awaited()
            await c.voice_action('voice.signal',{'session':'new','target':1,'target_session':'recipient-new','signal':{'restart':True}})
        payload=c.channel_layer.group_send.call_args.args[1]['payload']
        self.assertEqual(payload['session'],'new');self.assertEqual(payload['target_session'],'recipient-new')
        self.assertEqual(c.channel_layer.group_send.await_count,1) # no full-room update per ICE candidate

    async def test_queued_signal_not_delivered_after_recipient_reconnect(self):
        c=self.consumer()
        await c.voice_event({'payload':{'type':'voice.signal','target':0,'target_session':'old'}})
        c.send_json.assert_not_awaited()

    async def test_join_ack_identifies_all_sessions(self):
        c=self.consumer()
        state={'seat':0,'players':[{'voice':True,'voice_session':'fresh'},{'voice':True,'voice_session':'friend'}]}
        with patch('game.consumer.database_sync_to_async',return_value=AsyncMock(return_value=state)):
            await c.voice_action('voice.join',{'session':'fresh'})
        self.assertEqual(c.voice_session,'fresh')
        ack=c.send_json.call_args.args[0]
        self.assertEqual(ack['session'],'fresh');self.assertEqual(ack['sessions']['1'],'friend')
