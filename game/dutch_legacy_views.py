import json
import time
from django.core.cache import cache
from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from . import dutch_legacy_service as service
from .models import Room, Profile
from .dutch_legacy_rules import rules
from django.conf import settings


def rate(key,limit=90,period=60):
    bucket=int(time.time()/period);key=f'dutch:{key}:{bucket}'
    if cache.add(key,1,timeout=period*2):return
    try:n=cache.incr(key)
    except ValueError:cache.set(key,1,timeout=period*2);return
    if n>limit:raise ValueError('Too many actions. Please wait a moment.')


@never_cache
@ensure_csrf_cookie
def index(request,code=None,watch=False):
    service.identity(request)
    if code:
        room=Room.objects.filter(code=code.upper()).first()
        if not room or room.state.get('game_type')!='dutch':raise Http404('Dutch table not found.')
    nickname=''
    if request.user.is_authenticated:
        profile=Profile.objects.filter(user=request.user).first();nickname=profile.nickname if profile else request.user.username[:24]
    return render(request,'dutch/legacy.html',{'dutch_config':{'code':code.upper() if code else None,'watch':watch,'nickname':nickname,'rules':rules(getattr(settings,'DUTCH_RULES',None))}})


@never_cache
@require_POST
def api(request,action):
    try:
        if len(request.body)>4096:raise ValueError('Request too large.')
        data=json.loads(request.body)
        if not isinstance(data,dict):raise ValueError('Expected an object.')
        who=service.identity(request);rate(who)
        if action=='create':
            state=service.create(who,data.get('name'),data.get('limit',4))
        else:
            code=str(data.get('code','')).upper()
            if action=='poll':
                state=service.mutate(code,who,'resync')
                if state['seat'] is not None and not data.get('watch'):
                    state=service.mutate(code,who,'heartbeat',channel='http:'+who)
                elif data.get('watch'):
                    state=service.mutate(code,None,'resync')
                return JsonResponse(state)
            if action=='chat_history':return JsonResponse({'messages':service.chat_history(code,who)})
            if action=='chat':
                message=service.chat_post(code,who,data.get('text'),data.get('command'))
                async_to_sync(get_channel_layer().group_send)('dutch_'+code,{'type':'dutch_chat','message':message})
                return JsonResponse({'sent':True,'command':data['command']})
            allowed={'join','resync','ready','start','initial_peek','draw','take_discard','swap_drawn','cut','jack_peek','call','next_round','rematch','leave','delete'}
            if action not in allowed:raise ValueError('Unknown Dutch action.')
            state=service.mutate(code,None if action=='resync' and data.get('watch') else who,action,data)
            async_to_sync(get_channel_layer().group_send)('dutch_'+code,{'type':'dutch_update'})
        return JsonResponse(state)
    except (ValueError,KeyError,TypeError,json.JSONDecodeError) as error:return JsonResponse({'error':str(error)},status=400)
    except Room.DoesNotExist:return JsonResponse({'error':'Table not found.','deleted':True},status=404)


class TenIsolationMiddleware:
    """Routing boundary only; leaves all existing 10 room state and rules alone."""
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        code=None;path=request.path
        prefixes=('/room/','/watch/','/spectate/api/')
        for prefix in prefixes:
            if path.startswith(prefix):code=path[len(prefix):].strip('/');break
        if path.startswith('/api/') and request.method=='POST':
            try:
                value=json.loads(request.body)
                if isinstance(value,dict):code=value.get('code')
            except (ValueError,UnicodeDecodeError):pass
        if isinstance(code,str) and Room.objects.filter(code=code.upper().strip(),state__game_type='dutch').exists():
            return JsonResponse({'error':'Use the Dutch table route for this room.'},status=404)
        return self.get_response(request)
