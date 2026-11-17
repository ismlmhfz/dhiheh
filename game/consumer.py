import asyncio, time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .service import mutate
from . import chat
from .models import Room
class RoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.code=self.scope['url_route']['kwargs']['code']
        self.identity=self.scope['session'].get('player_id',self.scope['session'].session_key)
        self.voice=False
        self.voice_session=None
        self.signal_times=[]
        try:
            from .social import room_identity
            self.identity=await database_sync_to_async(room_identity)(self.code,self.identity,self.scope['user'])
            initial=await database_sync_to_async(mutate)(self.code,self.identity,'connect')
            self.seat=initial['seat']
        except Exception:
            await self.close(code=4403); return
        await self.channel_layer.group_add('room_'+self.code,self.channel_name)
        await self.accept()
        await self.send_json({'type':'chat.history','messages':await database_sync_to_async(chat.history)(self.code,self.identity)})
        await self.channel_layer.group_send('room_'+self.code,{'type':'update'})
        self.timer=asyncio.create_task(self.watch())
    async def watch(self):
        while True:
            await asyncio.sleep(1)
            await self.update({})
    async def update(self,event):
        try:
            state=await database_sync_to_async(mutate)(self.code,self.identity,'resync')
            self.seat=state['seat']
            await self.send_json(state)
        except Room.DoesNotExist: await self.table_deleted({})
        except Exception: await self.close()
    async def table_deleted(self,event):
        await self.send_json({'type':'table.deleted'})
        await self.close(code=4404)

    async def receive_json(self,content):
        try:
            action=content.get('action','resync')
            if action=='chat.send':
                try:
                    message=await database_sync_to_async(chat.post)(self.code,self.identity,content.get('text'),content.get('command'))
                    await self.send_json({'type':'chat.sent','command':content['command']})
                    await self.channel_layer.group_send('room_'+self.code,{'type':'chat_event','message':message})
                except ValueError as error:
                    await self.send_json({'type':'chat.error','error':str(error)})
                return
            if action.startswith('voice.'):
                await self.voice_action(action,content)
                return
            if action not in ('ready','start','play','bank','chase','next','rematch','quit','seat','resync','lobby','bots','appearance','team','team_name'): raise ValueError('Unknown action.')
            await database_sync_to_async(mutate)(self.code,self.identity,action,content)
            await self.channel_layer.group_send('room_'+self.code,{'type':'update'})
        except (ValueError,KeyError,TypeError) as e:
            await self.send_json({'type':'voice.error','error':str(e),'session':content.get('session')} if content.get('action','').startswith('voice.') else {'error':str(e)})
    async def voice_action(self,action,content):
        # Ignore late messages from a previous microphone/peer session.
        if action!='voice.join' and content.get('session')!=self.voice_session: return
        now=time.monotonic()
        self.signal_times=[t for t in self.signal_times if now-t<10]
        if len(self.signal_times)>=100: raise ValueError('Voice signaling rate exceeded.')
        self.signal_times.append(now)
        if action=='voice.join':
            session=content.get('session')
            if session is not None and (not isinstance(session,str) or not 1<=len(session)<=64): raise ValueError('Invalid voice session.')
            state=await database_sync_to_async(mutate)(self.code,self.identity,'voice_join',{'owner':self.channel_name,'session':session})
            self.voice=True; self.voice_session=session; self.seat=state['seat']
            revision=state.get('seating_revision',0)
            await self.send_json({'type':'voice.peers','session':session,'sessions':{str(i):p.get('voice_session') for i,p in enumerate(state['players']) if p and p.get('voice')},'revision':revision,'peers':[i for i,p in enumerate(state['players']) if p and p.get('voice') and i!=self.seat]})
            await self.channel_layer.group_send('room_'+self.code,{'type':'voice_event','payload':{'type':'voice.joined','session':session,'revision':revision,'seat':self.seat}})
        elif action=='voice.leave':
            await self.leave_voice()
        elif action=='voice.mute' and self.voice:
            await database_sync_to_async(mutate)(self.code,self.identity,'voice_mute',{'owner':self.channel_name,'muted':content.get('muted')})
        elif action=='voice.signal' and self.voice:
            target=content.get('target');signal=content.get('signal')
            if type(target) is not int or target not in range(4) or target==self.seat or not isinstance(signal,dict): raise ValueError('Invalid voice recipient.')
            import json
            if len(json.dumps(signal))>16000: raise ValueError('Voice signal too large.')
            state=await database_sync_to_async(mutate)(self.code,self.identity,'resync')
            if content.get('revision',0)!=state.get('seating_revision',0): return
            if not state['players'][target] or not state['players'][target].get('voice'): return
            target_session=content.get('target_session') if self.voice_session is not None else state['players'][target].get('voice_session')
            if target_session!=state['players'][target].get('voice_session'): return
            await self.channel_layer.group_send('room_'+self.code,{'type':'voice_event','payload':{'type':'voice.signal','session':self.voice_session,'target_session':target_session,'revision':state.get('seating_revision',0),'seat':state['seat'],'target':target,'signal':signal}})
        else: raise ValueError('Join voice before sending audio signals.')
        if action!='voice.signal':
            await self.channel_layer.group_send('room_'+self.code,{'type':'update'})
    async def chat_event(self,event):
        await self.send_json({'type':'chat.message','message':event['message']})

    async def voice_event(self,event):
        payload=event['payload']
        if payload.get('type')=='voice.signal' and (not self.voice or payload.get('target')!=self.seat or payload.get('target_session')!=self.voice_session): return
        await self.send_json(payload)
    async def leave_voice(self):
        if self.voice:
            self.voice=False
            # A lobby leave can remove the seat before the socket closes.
            # Peers must still receive a departure and release their audio.
            try:
                await database_sync_to_async(mutate)(self.code,self.identity,'voice_leave',{'owner':self.channel_name})
            except (ValueError, Room.DoesNotExist):
                pass
            await self.channel_layer.group_send('room_'+self.code,{'type':'voice_event','payload':{'type':'voice.left','seat':self.seat,'session':self.voice_session}})
    async def disconnect(self,code):
        if hasattr(self,'timer'): self.timer.cancel()
        if hasattr(self,'identity'):
            try:
                await self.leave_voice()
                await database_sync_to_async(mutate)(self.code,self.identity,'disconnect')
                await self.channel_layer.group_send('room_'+self.code,{'type':'update'})
                await self.channel_layer.group_discard('room_'+self.code,self.channel_name)
            except Exception: pass
