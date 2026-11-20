"""Dutch-only transactional room lifecycle. All persisted changes hold a row lock."""
import copy
import secrets
import string
import time
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from .models import Room
from .service import identity, seat_of, serialized
from . import dutch_engine as engine


def check_room(room):
    if room.state.get('game_type','ten')!='dutch': raise ValueError('This is not a Dutch table.')
    return room


def name(value):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>24:raise ValueError('Use a name of 1–24 characters.')
    return ' '.join(value.split())


def envelope(room,viewer,now):
    result=engine.public(room.state,viewer,now);result['code']=room.code
    result['invite_open']=room.state['status']=='lobby' and not room.state.get('invitation_closed') and any(p is None for p in room.state['players']) and now<room.state['created_at']+3600
    return result


@serialized
def create(who,player_name,limit=4):
    now=time.time()
    if Room.objects.filter(created_at__gt=timezone.now()-timedelta(minutes=10),state__players__0__id=who).count()>=6:
        raise ValueError('Please wait before creating more tables.')
    state=engine.new_state(limit,who,name(player_name),now,getattr(settings,'DUTCH_RULES',None))
    for _ in range(10):
        code=''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6))
        try:
            with transaction.atomic():room=Room.objects.create(code=code,state=state)
            return envelope(room,0,now)
        except IntegrityError:continue
    raise ValueError('Please try creating the table again.')


def abandon(s,seat=None):
    s.update(status='abandoned',phase='abandoned',turn=None,turn_deadline=None,reserved=None,
             power=None,cut_window=None,cut_reveal=None,initial_peeks={})
    s.pop('all_idle_since',None);engine.event(s,'match.abandoned',seat)


def presence(s,now):
    # Leases drive connection dots for rendering only; play never pauses (no-pause rules).
    for p in s['players']:
        if not p:continue
        leases=p.get('connections',{})
        last_expiry=max(leases.values(),default=now)
        p['connections']={k:v for k,v in leases.items() if v>now}
        p['connected']=bool(p['connections'])
        if p['connected']:p.pop('offline_since',None)
        else:p.setdefault('offline_since',min(now,last_expiry))
    # Safeguard: if no seat has been connected for a full turn cycle, abandon the dead round.
    if s['status'] in engine.ACTIVE and s['rules']['abandon_when_all_idle']:
        seats=[p for p in s['players'] if p]
        if seats and not any(p['connected'] for p in seats):
            if now-max(p['offline_since'] for p in seats)>=s['rules']['turn_seconds']:
                abandon(s)


def command_id(data):
    value=data.get('command')
    try:uuid.UUID(value)
    except (ValueError,TypeError,AttributeError):raise ValueError('A command UUID is required.')
    return value


@serialized
def mutate(code,who,action,data=None,*,channel=None,now=None):
    legacy=Room.objects.filter(code=code,state__game_type='dutch',state__schema_version=1).exists()
    if legacy:
        from . import dutch_legacy_service
        return dutch_legacy_service.mutate(code,who,action,data,channel=channel,now=now)
    data=data or {};now=time.time() if now is None else now
    with transaction.atomic():
        room=check_room(Room.objects.select_for_update().get(code=code))
        s=room.state;before=copy.deepcopy(s);seat=seat_of(s,who) if who else None
        presence(s,now);engine.tick(s,now)
        if action=='join':
            if seat is None:
                if not envelope(room,None,now)['invite_open']:raise ValueError('This invitation is closed. You can still spectate.')
                seat=s['players'].index(None)
                s['players'][seat]={'id':who,'name':name(data.get('name')),'ready':False,'connected':False,'connections':{},'offline_since':now}
            if all(s['players']):s['invitation_closed']=True
        elif action in ('resync','tick'):
            pass
        else:
            if seat is None:raise ValueError('Only seated players can act.')
            p=s['players'][seat]
            if action in ('connect','heartbeat','disconnect'):
                if not channel:raise ValueError('Missing connection handle.')
                if action=='disconnect':p.setdefault('connections',{}).pop(channel,None)
                else:p.setdefault('connections',{})[channel]=now+15
                presence(s,now)
            else:
                cmd=command_id(data);key=who+':'+cmd
                if key not in s['commands']:
                    if action=='ready':
                        engine.require(s['status']=='lobby','Readiness is only available in the lobby.')
                        p['ready']=not p['ready']
                    elif action in ('start','next_round','rematch','delete'):
                        engine.require(seat==s['host'],'Only the host may do that.')
                        if action=='start':engine.start(s,seat,now)
                        elif action=='next_round':
                            engine.require(s['status']=='round_results','Finish the current round first.')
                            engine.next_round(s,now)
                        elif action=='rematch':
                            engine.require(s['status'] in {'match_results','abandoned'},'Finish the current round first.')
                            players=s['players'];host=s['host'];old_rules=s['rules'];old_revision=s['revision']
                            fresh=engine.new_state(len(players),players[host]['id'],players[host]['name'],s['created_at'],old_rules)
                            fresh.update(players=players,host=host,revision=old_revision,invitation_closed=True,commands=s['commands'])
                            for player in players:player['ready']=False
                            s.clear();s.update(fresh)
                        else:room.delete();return {'deleted':True,'code':code}
                    elif action=='leave':
                        if s['status']=='lobby':
                            s['players'][seat]=None
                            occupied=[i for i,p in enumerate(s['players']) if p]
                            if not occupied:room.delete();return {'deleted':True,'code':code}
                            if seat==s['host']:s['host']=occupied[0]
                            for player in s['players']:
                                if player:player['ready']=False
                            s['invitation_closed']=False
                        else:
                            p['connections']={};p['connected']=False;abandon(s,seat)
                    else:engine.act(s,seat,action,data,now)
                    s['commands']=(s['commands']+[key])[-512:]
        if s!=before:
            s['revision']=before['revision']+1;room.version+=1;room.save(update_fields=['state','version'])
        return envelope(room,seat,now)


def chat_history(code,who):
    from . import chat
    check_room(Room.objects.get(code=code))
    return chat.history(code,who)


@serialized
@transaction.atomic
def chat_post(code,who,text,command):
    from . import chat
    check_room(Room.objects.select_for_update().get(code=code))
    return chat.post(code,who,text,command)
