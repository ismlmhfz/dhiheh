"""Account-scoped friends and conversations; no player secrets in chat payloads."""
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from .models import Friendship, Conversation, ConversationMember, ConversationMessage, GroupMatch, Room
from . import service

User = get_user_model()


def person(user):
    profile = getattr(user, 'profile', None)
    return {'id':user.pk, 'username':user.username, 'name':profile.nickname if profile else user.username,
            'avatar':profile.avatar if profile else 'fox'}


def pair(a,b):
    return {'first_id':min(a,b),'second_id':max(a,b)}


def friends(a,b):
    return a != b and Friendship.objects.filter(**pair(a,b),accepted=True).exists()


def member(conversation_id,user):
    return get_object_or_404(ConversationMember.objects.select_related('conversation'),conversation_id=conversation_id,user=user)


def room_identity(code, fallback, user):
    match = GroupMatch.objects.filter(room__code=code).first()
    if not match:
        return fallback
    if not user.is_authenticated or not ConversationMember.objects.filter(conversation=match.conversation,user=user).exists():
        raise ValueError('This match is for group members. You can watch using its spectator link.')
    return f'account:{user.pk}'


@login_required
@ensure_csrf_cookie
@never_cache
def home(request):
    return render(request,'social.html')


def summary(c,user):
    members=list(c.members.select_related('user','user__profile'))
    own=next(m for m in members if m.user_id==user.pk)
    other=next((m.user for m in members if m.user_id!=user.pk),None)
    latest=c.messages.select_related('sender').order_by('-id').first()
    return {'id':c.pk,'kind':c.kind,'title':c.title if c.kind=='group' else (person(other)['name'] if other else 'Private chat'),
            'owner':c.owner_id,'members':[person(m.user) for m in members],
            'unread':c.messages.filter(id__gt=own.last_read_id).exclude(sender=user).count(),
            'preview':('Match invitation' if latest.match_id else latest.text[:70]) if latest else 'Say hello',
            'can_send':c.kind=='group' or (other is not None and friends(user.pk,other.pk))}


@login_required
@require_GET
@never_cache
def overview(request):
    relations=Friendship.objects.filter(Q(first=request.user)|Q(second=request.user)).select_related('first','second','first__profile','second__profile')
    accepted=[];incoming=[];outgoing=[]
    for f in relations:
        data={'id':f.pk,'person':person(f.second if f.first_id==request.user.pk else f.first)}
        (accepted if f.accepted else outgoing if f.requested_by_id==request.user.pk else incoming).append(data)
    conversations=Conversation.objects.filter(members__user=request.user).order_by('-updated_at')[:100]
    return JsonResponse({'me':person(request.user),'friends':accepted,'incoming':incoming,'outgoing':outgoing,
                         'conversations':[summary(c,request.user) for c in conversations]})


def message_data(m,user=None):
    data={'id':m.pk,'sender':person(m.sender) if m.sender else {'id':None,'name':'Former player','username':'','avatar':'fox'},
          'text':m.text,'time':m.created_at.isoformat()}
    if m.match_id:
        room=m.match.room;s=room.state
        data['match']={'code':room.code,'status':s['status'],'players':sum(bool(p) for p in s['players']),
                       'join_url':f'/room/{room.code}/','watch_url':f'/watch/{room.code}/'}
        from .invitations import details
        data['match']['invitation']=details(room)
        data['match']['seated']=bool(user and service.seat_of(s,f'account:{user.pk}') is not None)
    return data


@login_required
@require_GET
@never_cache
def conversation(request,pk):
    membership=member(pk,request.user)
    messages=list(membership.conversation.messages.select_related('sender','sender__profile','match','match__room').order_by('-id')[:100])
    return JsonResponse({'conversation':summary(membership.conversation,request.user),
                         'messages':[message_data(m,request.user) for m in reversed(messages)]})


def clean_text(value,limit,label):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError(f'{label} must be between 1 and {limit} characters.')
    return value.strip()


def command(data):
    return clean_text(data.get('command'),64,'Message identifier')


@login_required
@require_POST
@transaction.atomic
def action(request,action):
    try:
        data=json.loads(request.body)
        if not isinstance(data,dict):raise ValueError('Invalid request.')
        # A per-account row lock serializes rate limits and simultaneous requests.
        User.objects.select_for_update().get(pk=request.user.pk)
        user=request.user
        if action=='friend_request':
            username=clean_text(data.get('username'),150,'Username')
            other=User.objects.filter(username__iexact=username,is_active=True).first()
            if not other:raise ValueError('No player found with that username.')
            if other.pk==user.pk:raise ValueError('Enter another player’s username.')
            if Friendship.objects.filter(requested_by=user,created_at__gte=timezone.now()-timedelta(hours=1)).count()>=20:
                raise ValueError('Please wait before sending more friend requests.')
            Friendship.objects.get_or_create(**pair(user.pk,other.pk),defaults={'requested_by':user})
            return JsonResponse({'ok':True})
        if action in ('friend_accept','friend_decline','friend_remove'):
            f=get_object_or_404(Friendship.objects.select_for_update().filter(Q(first=user)|Q(second=user)),pk=data.get('id'))
            if action=='friend_accept':
                if f.requested_by_id==user.pk:raise ValueError('The other player needs to accept this request.')
                f.accepted=True;f.save(update_fields=['accepted'])
            else:f.delete()
            return JsonResponse({'ok':True})
        if action=='direct':
            other=get_object_or_404(User,pk=data.get('user_id'))
            if not friends(user.pk,other.pk):raise ValueError('Add this player as a friend first.')
            key=':'.join(map(str,sorted([user.pk,other.pk])))
            c,created=Conversation.objects.get_or_create(direct_key=key,defaults={'kind':'direct','owner':user})
            for u in (user,other):ConversationMember.objects.get_or_create(conversation=c,user=u)
            return JsonResponse({'id':c.pk})
        if action=='group_create':
            if Conversation.objects.filter(owner=user,created_at__gte=timezone.now()-timedelta(hours=1)).count()>=10:
                raise ValueError('Please wait before creating more groups.')
            title=clean_text(data.get('title'),48,'Group name')
            ids=data.get('user_ids',[])
            if not isinstance(ids,list) or len(ids)>19 or any(type(i) is not int for i in ids):raise ValueError('Choose up to 19 friends.')
            ids=set(ids)-{user.pk}
            if not ids:raise ValueError('Choose at least one friend for your group.')
            if any(not friends(user.pk,i) for i in ids):raise ValueError('Only accepted friends can be added.')
            c=Conversation.objects.create(kind='group',title=title,owner=user)
            for uid in ids|{user.pk}:ConversationMember.objects.create(conversation=c,user_id=uid)
            return JsonResponse({'id':c.pk})
        membership=member(data.get('conversation_id'),user)
        c=Conversation.objects.select_for_update().get(pk=membership.conversation_id)
        if action=='read':
            maximum=c.messages.order_by('-id').values_list('id',flat=True).first() or 0
            value=data.get('message_id',0)
            if type(value) is not int or value<0:raise ValueError('Invalid message identifier.')
            membership.last_read_id=max(membership.last_read_id,min(value,maximum));membership.save(update_fields=['last_read_id'])
            return JsonResponse({'ok':True})
        if action=='send':
            if c.kind=='direct':
                other=c.members.exclude(user=user).first()
                if not other or not friends(user.pk,other.user_id):raise ValueError('You must be friends to send a private message.')
            text=clean_text(data.get('text'),1000,'Message');nonce=command(data)
            if c.messages.filter(sender=user,command=nonce).exists():return JsonResponse({'ok':True})
            if ConversationMessage.objects.filter(sender=user,created_at__gte=timezone.now()-timedelta(minutes=1)).count()>=30:
                raise ValueError('Please wait a moment before sending more messages.')
            c.messages.create(sender=user,text=text,command=nonce)
        elif action=='group_add':
            if c.kind!='group' or c.owner_id!=user.pk:raise ValueError('Only the group owner can add members.')
            uid=data.get('user_id')
            if type(uid) is not int or not friends(user.pk,uid):raise ValueError('Choose an accepted friend.')
            if c.members.count()>=20:raise ValueError('This group has reached 20 members.')
            ConversationMember.objects.get_or_create(conversation=c,user_id=uid)
        elif action=='group_rename':
            if c.kind!='group' or c.owner_id!=user.pk:raise ValueError('Only the group owner can rename it.')
            c.title=clean_text(data.get('title'),48,'Group name')
        elif action=='group_leave':
            if c.kind!='group':raise ValueError('This is not a group.')
            # Leave after the player has left any active match, preventing locked seats.
            for match in c.matches.select_related('room').filter(room__state__status__in=['lobby','playing','chase_decision','deal_results']):
                if service.seat_of(match.room.state,f'account:{user.pk}') is not None:raise ValueError('Leave or finish your group match before leaving this group.')
            membership.delete()
            if c.owner_id==user.pk:
                successor=c.members.order_by('joined_at').first();c.owner_id=successor.user_id if successor else None
        elif action=='match_create':
            if c.kind!='group':raise ValueError('Start a match in a group chat.')
            nonce=command(data)
            existing=c.messages.filter(sender=user,command=nonce,match__isnull=False).select_related('match__room').first()
            if existing:return JsonResponse({'code':existing.match.room.code})
            from .invitations import details
            for active in c.matches.filter(room__state__status__in=['lobby','playing','chase_decision','deal_results']).select_related('room'):
                if active.room.state['status']!='lobby' or (any(active.room.state['players']) and (details(active.room)['open'] or all(active.room.state['players']))):
                    raise ValueError('This group already has an active match. Use its invitation to join or watch.')
            code,_=service.create(f'account:{user.pk}',person(user)['name'],data.get('mode','standard'))
            match=GroupMatch.objects.create(room=Room.objects.get(code=code),conversation=c,created_by=user)
            service.mutate(code,f'account:{user.pk}','appearance',{'avatar':person(user)['avatar']})
            c.messages.create(sender=user,text='Started a match. Join a seat or watch the table.',command=nonce,match=match)
            c.updated_at=timezone.now();c.save()
            return JsonResponse({'code':code})
        else:raise ValueError('Unknown action.')
        c.updated_at=timezone.now();c.save()
        return JsonResponse({'ok':True})
    except (ValueError,TypeError,KeyError,json.JSONDecodeError) as error:
        # Roll back any partial operation before returning a validation error.
        transaction.set_rollback(True)
        return JsonResponse({'error':str(error)},status=400)
