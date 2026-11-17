import json
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from .accounts import SignupForm, ProfileForm
from .models import Profile
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from . import service
from .models import Room
@ensure_csrf_cookie
def index(request,code=None):
    player_identity=service.identity(request)
    group_id=None
    if code:
        from .models import GroupMatch, ConversationMember
        match=GroupMatch.objects.filter(room__code=code.upper()).first()
        if match:
            if not request.user.is_authenticated or not ConversationMember.objects.filter(conversation=match.conversation,user=request.user).exists():
                return redirect('/watch/'+code.upper()+'/')
            group_id=match.conversation_id
            player_identity=f'account:{request.user.pk}'
        room=Room.objects.filter(code=code.upper()).first()
        from .invitations import details
        if room and service.seat_of(room.state,player_identity) is None and not details(room)['open']:
            return redirect('/watch/'+code.upper()+'/')
    appearance={'nickname':'','avatar':'fox','deck':'cosmic'}
    if request.user.is_authenticated:
        profile,_=Profile.objects.get_or_create(user=request.user,defaults={'nickname':request.user.username[:24]})
        appearance={k:getattr(profile,k) for k in appearance}
    return render(request,'index.html',{'group_id':group_id,'appearance':appearance,'voice_config':{'iceServers':settings.VOICE_ICE_SERVERS}})
class PlayerLoginView(LoginView):
    template_name='registration/login.html'
    def form_valid(self,form):
        service.identity(self.request)
        return super().form_valid(form)
def signup(request):
    form=SignupForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        service.identity(request)
        user=form.save()
        Profile.objects.create(user=user,nickname=user.username[:24])
        login(request,user)
        return redirect('/profile/')
    return render(request,'registration/signup.html',{'form':form})
@login_required
def profile(request):
    instance,_=Profile.objects.get_or_create(user=request.user,defaults={'nickname':request.user.username[:24]})
    form=ProfileForm(request.POST or None,instance=instance)
    saved=False
    if request.method=='POST' and form.is_valid():
        form.save(); saved=True
    return render(request,'registration/profile.html',{'form':form,'saved':saved})
@require_POST
def api(request,action):
    try:
        data=json.loads(request.body)
        identity=service.identity(request)
        if action=='preferences':
            if not request.user.is_authenticated: return JsonResponse({'error':'Log in to save your profile.'},status=403)
            profile,_=Profile.objects.get_or_create(user=request.user,defaults={'nickname':request.user.username[:24]})
            values={k:data.get(k,getattr(profile,k)) for k in ('nickname','avatar','deck')}
            form=ProfileForm(values,instance=profile)
            if not form.is_valid(): raise ValueError('Choose a valid avatar, deck and nickname.')
            form.save()
            return JsonResponse({'saved':True})
        if action in ('create','practice'):
            code,state=service.create(identity,data.get('name','Player'),data.get('mode','standard'),practice=action=='practice')
        else:
            code=str(data.get('code','')).upper().strip()
            from .social import room_identity
            identity=room_identity(code,identity,request.user)
            if action=='delete':
                service.delete_table(code,identity)
                async_to_sync(get_channel_layer().group_send)('room_'+code,{'type':'table_deleted'})
                return JsonResponse({'deleted':True})
            if action=='voice_config':
                service.mutate(code,identity,'resync')
                from .voice import configuration
                response=JsonResponse(configuration(identity))
                response['Cache-Control']='no-store'
                return response
            state=service.mutate(code,identity,action,data)
            async_to_sync(get_channel_layer().group_send)('room_'+code,{'type':'update'})
        if action in ('create','practice','join'):
            avatar=data.get('avatar','fox')
            if request.user.is_authenticated:
                profile=Profile.objects.filter(user=request.user).first()
                if profile: avatar=profile.avatar
            state=service.mutate(code,identity,'appearance',{'avatar':avatar})
        return JsonResponse({'code':code,'state':state})
    except (ValueError,Room.DoesNotExist,KeyError,TypeError,json.JSONDecodeError) as e:
        return JsonResponse({'error':'Room not found.' if isinstance(e,Room.DoesNotExist) else str(e)},status=400)
