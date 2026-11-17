import secrets, string, time, threading, functools, copy
from django.db import transaction
from .models import Room
from . import engine
def identity(request):
    if not request.session.session_key: request.session.create()
    if not request.session.get('player_id'):
        request.session['player_id']=request.session.session_key
    return request.session['player_id']
def seat_of(s,identity):
    return next((i for i,p in enumerate(s['players']) if p and p['id']==identity),None)
_local_lock = threading.RLock()
def serialized(fn):
    @functools.wraps(fn)
    def wrapped(*args,**kwargs):
        with _local_lock: return fn(*args,**kwargs)
    return wrapped
def fill_bots(s):
    counts=[sum(bool(p) and p.get('team',seat%2)==t for seat,p in enumerate(s['players'])) for t in range(2)]
    for i,p in enumerate(s['players']):
        if p is None:
            team=0 if counts[0]<=counts[1] else 1
            s['players'][i]={'id':'bot:'+secrets.token_hex(16),'name':['Willow','Jasper','Clover','Maple'][i]+' (Bot)','team':team,'bot':True,'ready':True,'connected':True,'connections':0}
            counts[team]+=1
    s['practice']=True

def bot_step(s):
    """Advance at most one bot action, using only its own legal hand."""
    if s.get('paused') or time.time()<s.get('bot_due',0): return
    if s['status']=='playing' and s['players'][s['turn']].get('bot'):
        seat=s['turn']
        lead=s['trick'][0]['card'][-1] if s['trick'] else None
        engine.play(s,seat,secrets.choice(engine.legal(s['hands'][seat],lead)))
        s['bot_due']=time.time()+1
    elif s['status']=='chase_decision' and s['players'][s['decision']['seat']].get('bot'):
        engine.decide(s,secrets.choice([True,False]))
        s['bot_due']=time.time()+1

@serialized
def mutate(code,identity,action,data=None):
    data = data or {}
    with transaction.atomic():
        room = Room.objects.select_for_update().get(code=code)
        s = room.state
        original = copy.deepcopy(s)
        seat = seat_of(s,identity)
        if all(s['players']): s['invitation_closed']=True
        if action=='join' and seat is None:
            from .invitations import details
            invite=details(room)
            if not invite['open']: raise ValueError(invite['reason']+'. This invitation is closed. You can still watch the table.')
            if s['status']!='lobby': raise ValueError('This match has already started.')
            if all(s['players']): raise ValueError('This room is full.')
            seat = s['players'].index(None)
            counts=[sum(bool(p) and p.get('team',i%2)==t for i,p in enumerate(s['players'])) for t in range(2)]
            s['players'][seat]={'id':identity,'name':str(data.get('name','Player')).strip()[:24] or 'Player','team':0 if counts[0]<=counts[1] else 1,'ready':False,'connected':True,'connections':0}
        if seat is None: raise ValueError('Join this room first.')
        for i,player in enumerate(s['players']):
            if player: player.setdefault('team',i%2)
        engine.tick(s)
        if s.get('play_direction')!='counterclockwise':
            if s.get('trick') and s['status']=='playing':
                s['turn']=engine.next_turn(s['trick'])
            s['play_direction']='counterclockwise'
        # Upgrade existing rooms without interrupting a stack already in play.
        if s.get('lead_rule')!='winner':
            if s.get('last') and not s.get('trick') and s['status']=='playing':
                s['starter']=s['turn']=s['last']['winner']
            s['lead_rule']='winner'
        command = data.get('command')
        duplicate = command and command in s.get('commands',[])
        if not duplicate:
            p = s['players'][seat]
            if action=='appearance':
                if data.get('avatar') in ('fox','panda','frog','cat','lion','owl','koala','dragon'): p['avatar']=data['avatar']
            elif action=='voice_join':
                if p.get('voice') and p.get('voice_owner')!=data['owner']:
                    raise ValueError('Voice is already active in another tab. Disconnect it there first.')
                p.update(voice=True,voice_owner=data['owner'],voice_muted=False,voice_session=data.get('session'))
            elif action=='voice_leave':
                if p.get('voice_owner')==data.get('owner'): p.update(voice=False,voice_owner=None,voice_muted=False)
            elif action=='voice_mute':
                if p.get('voice_owner')==data.get('owner'): p['voice_muted']=bool(data.get('muted'))
            elif action=='team_name':
                if s['status']!='lobby': raise ValueError('Team names are locked after the match starts.')
                name=data.get('name')
                if not isinstance(name,str) or not name.strip() or len(name.strip())>18:
                    raise ValueError('Use a team name between 1 and 18 characters.')
                name=' '.join(name.split())
                team=p.get('team',seat%2)
                names=s.setdefault('team_names',['Fern','Amber'])
                if name.casefold()==names[1-team].casefold():
                    raise ValueError('Choose a different name from the other team.')
                names[team]=name
            elif action=='ready':
                if s['status']!='lobby': raise ValueError('The match has already started.')
                p['ready']=not p['ready']
            elif action=='team':
                if s['status']!='lobby': raise ValueError('Teams cannot change after the match starts.')
                team=data.get('team')
                if type(team) is not int or team not in (0,1): raise ValueError('Choose Team Fern or Team Amber.')
                if p['team']!=team:
                    p['team']=team
                    for player in s['players']:
                        if player and not player.get('bot'): player['ready']=False
            elif action=='bots':
                if seat!=s['host'] or s['status']!='lobby': raise ValueError('Only the host can add bots in the lobby.')
                fill_bots(s)
            elif action in ('start','rematch'):
                if seat != s['host']: raise ValueError('Only the host can start a match.')
                if action=='start' and s['status']!='lobby': raise ValueError('Match already started.')
                if action=='rematch' and s['status'] not in ('match_results','abandoned'): raise ValueError('Finish the match first.')
                if not all(x and x['ready'] and x['connected'] for x in s['players']): raise ValueError('All four players must be connected and ready.')
                teams=[[p for p in s['players'] if p['team']==t] for t in range(2)]
                if [len(t) for t in teams]!=[2,2]: raise ValueError('Each team needs exactly two players before starting.')
                arranged=[teams[0][0],teams[1][0],teams[0][1],teams[1][1]]
                if arranged!=s['players']:
                    host_id=s['players'][s['host']]['id']
                    s['seating_map']={str(i):arranged.index(player) for i,player in enumerate(s['players'])}
                    s['players']=arranged
                    s['host']=seat_of(s,host_id)
                    seat=seat_of(s,identity)
                    s['seating_revision']=s.get('seating_revision',0)+1
                engine.new_match(s)
            elif action=='play': engine.play(s,seat,data.get('card'))
            elif action in ('bank','chase'):
                if s['status']!='chase_decision' or s['decision']['seat']!=seat or s.get('paused'): raise ValueError('Only the stack winner may choose now.')
                engine.decide(s,action=='chase')
            elif action=='next':
                if seat!=s['host'] or s['status']!='deal_results': raise ValueError('The host starts the next deal.')
                engine.new_deal(s)
            elif action=='lobby':
                if seat!=s['host'] or s['status'] not in ('abandoned','match_results'): raise ValueError('The host may return the finished match to the lobby.')
                s.update(status='lobby',paused=False,hands=[[],[],[],[]],trick=[],last=None,history=[],decision=None,chase=None)
                for player in s['players']:
                    if player: player['ready']=bool(player.get('bot'))
            elif action=='quit':
                if s['status']!='lobby': s.update(status='abandoned',paused=False)
            elif action=='leave':
                if s['status']!='lobby': raise ValueError('Quit the match before leaving.')
                s['players'][seat]=None
                if seat==s['host']: s['host']=next((i for i,x in enumerate(s['players']) if x),0)
            elif action=='seat':
                dest = int(data.get('seat',-1))
                if s['status']!='lobby' or dest not in range(4) or s['players'][dest]: raise ValueError('Choose an empty lobby seat.')
                s['players'][dest],s['players'][seat] = p,None
                if s['host']==seat: s['host']=dest
                seat=dest
            elif action=='connect':
                p['connections']=p.get('connections',0)+1
                p.update(connected=True,disconnected_at=None)
                if s.get('paused') and all(x and x['connected'] for x in s['players']):
                    if s.get('decision'): s['decision']['deadline'] += time.time()-s['paused_at']
                    s['paused']=False
            elif action=='disconnect':
                p['connections']=max(0,p.get('connections',1)-1)
                if not p['connections']:
                    p.update(connected=False,disconnected_at=time.time())
                    if s['status'] in ('playing','chase_decision','deal_results') and not s.get('paused'):
                        s.update(paused=True,paused_at=time.time())
            if command: s['commands']=(s.get('commands',[])+[command])[-100:]
        if action=='resync': bot_step(s)
        if all(s['players']): s['invitation_closed']=True
        if s != original:
            room.state=s; room.version+=1; room.save()
        result=engine.public(s,seat)
        from .invitations import details
        result['invitation']=details(room)
        return result
def create(identity,name,mode,practice=False):
    if mode not in engine.MODES: raise ValueError('Unknown match mode.')
    if Room.objects.filter(state__creator=identity,created_at__gte=__import__('django.utils.timezone',fromlist=['now']).now()-__import__('datetime').timedelta(minutes=1)).count()>=5: raise ValueError('Please wait a minute before creating more rooms.')
    while True:
        code=''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6))
        if not Room.objects.filter(code=code).exists(): break
    Room.objects.create(code=code,state={'creator':identity,'status':'lobby','mode':mode,'host':0,'players':[None]*4})
    state=mutate(code,identity,'join',{'name':name})
    if practice:
        mutate(code,identity,'bots')
        mutate(code,identity,'ready')
        state=mutate(code,identity,'start')
    return code,state

@serialized
def delete_table(code, identity):
    with transaction.atomic():
        room = Room.objects.select_for_update().get(code=code)
        seat = seat_of(room.state, identity)
        if seat is None or seat != room.state['host']:
            raise ValueError('Only the host can delete this table.')
        from .models import ConversationMessage
        ConversationMessage.objects.filter(match__room=room).update(text='This table was deleted by its host.')
        room.delete()
