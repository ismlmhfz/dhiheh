"""Per-viewer snapshots only. Group events carry notifications, never full state."""
import asyncio
import contextlib
import time
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from . import dutch_service as service
from .models import Room
from .consumer import RoomConsumer


class IsolatedTenConsumer(RoomConsumer):
    async def connect(self):
        code=self.scope['url_route']['kwargs']['code']
        if await database_sync_to_async(Room.objects.filter(code=code,state__game_type='dutch').exists)():
            await self.close(code=4404);return
        await super().connect()


class DutchConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.code=self.scope['url_route']['kwargs']['code'];self.group='dutch_'+self.code
        self.who=self.scope['session'].get('player_id',self.scope['session'].session_key)
        self.spectator=self.scope['url_route']['kwargs'].get('watch',False)
        self.joined=False;self.calls=[];self.last_heartbeat=0
        try:
            snapshot=await database_sync_to_async(service.mutate)(self.code,None if self.spectator else self.who,'resync')
            if not self.spectator:
                if snapshot['seat'] is None:await self.close(code=4403);return
                await database_sync_to_async(service.mutate)(self.code,self.who,'connect',channel=self.channel_name)
            await self.channel_layer.group_add(self.group,self.channel_name);self.joined=True
            await self.accept()
            if not self.spectator:
                await self.send_json({'type':'chat.history','messages':await database_sync_to_async(service.chat_history)(self.code,self.who)})
            await self.dutch_update({})
            await self.channel_layer.group_send(self.group,{'type':'dutch_update'})
            self.timer=asyncio.create_task(self.watch())
        except (ValueError,Room.DoesNotExist):await self.close(code=4404)

    async def watch(self):
        while True:
            await asyncio.sleep(.25)
            await self.dutch_update({})

    async def dutch_update(self,event):
        try:
            if not self.spectator and time.monotonic()-self.last_heartbeat>5:
                await database_sync_to_async(service.mutate)(self.code,self.who,'heartbeat',channel=self.channel_name)
                self.last_heartbeat=time.monotonic()
            snapshot=await database_sync_to_async(service.mutate)(self.code,None if self.spectator else self.who,'tick')
            await self.send_json({'type':'dutch.state','state':snapshot})
        except (Room.DoesNotExist,ValueError):
            await self.send_json({'type':'dutch.deleted'});await self.close(code=4404)

    async def receive(self,text_data=None,bytes_data=None,**kwargs):
        if bytes_data is not None or (text_data and len(text_data)>4096):await self.close(code=4400);return
        try:await super().receive(text_data=text_data,bytes_data=bytes_data,**kwargs)
        except ValueError:await self.send_json({'type':'dutch.error','error':'Invalid JSON.'})

    async def receive_json(self,data,**kwargs):
        try:
            if not isinstance(data,dict):raise ValueError('Expected an object.')
            if self.spectator:raise ValueError('Spectators cannot act or use private room chat.')
            now=time.monotonic();self.calls=[v for v in self.calls if now-v<10]
            if len(self.calls)>=60:raise ValueError('Too many actions. Please wait.')
            self.calls.append(now)
            action=data.get('action','')
            if action=='chat.send':
                message=await database_sync_to_async(service.chat_post)(self.code,self.who,data.get('text'),data.get('command'))
                await self.send_json({'type':'chat.sent','command':data['command']})
                await self.channel_layer.group_send(self.group,{'type':'dutch_chat','message':message});return
            allowed={'ready','start','choose_reveal','initial_peek','draw','take_discard','swap_drawn','discard_drawn','cut','jack_peek','queen_swap','king_lock','power_skip','call','next_round','rematch','leave','delete','resync'}
            if not action.startswith('dutch.') or action[6:] not in allowed:raise ValueError('Unknown Dutch action.')
            result=await database_sync_to_async(service.mutate)(self.code,self.who,action[6:],data)
            await self.send_json({'type':'dutch.ack','command':data.get('command'),'state':result})
            await self.channel_layer.group_send(self.group,{'type':'dutch_update'})
        except (ValueError,KeyError,TypeError) as error:await self.send_json({'type':'dutch.error','command':data.get('command') if isinstance(data,dict) else None,'error':str(error)})
        except Room.DoesNotExist:await self.send_json({'type':'dutch.deleted'});await self.close(code=4404)

    async def dutch_chat(self,event):
        if not self.spectator:await self.send_json({'type':'chat.message','message':event['message']})

    async def disconnect(self,code):
        timer=getattr(self,'timer',None)
        if timer:
            timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):await timer
        if getattr(self,'joined',False):
            if not self.spectator:
                with contextlib.suppress(Room.DoesNotExist,ValueError):
                    await database_sync_to_async(service.mutate)(self.code,self.who,'disconnect',channel=self.channel_name)
            await self.channel_layer.group_discard(self.group,self.channel_name)
            await self.channel_layer.group_send(self.group,{'type':'dutch_update'})
