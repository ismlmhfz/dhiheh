"""Public read-only table snapshots. Deliberate allowlist, never engine.public()."""
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from .models import Room, GroupMatch, ConversationMember


def snapshot(room):
    s=room.state
    keys=('status','mode','deal','trump','turn','starter','scores','stacks','tens','totals_tens','team_names','paused','result','winner','decision','chase')
    result={k:s[k] for k in keys if k in s}
    result['players']=[{k:p[k] for k in ('name','avatar','team','connected','ready','bot') if k in p} if p else None for p in s['players']]
    result['counts']=[len(h) for h in s.get('hands',[[],[],[],[]])]
    def trick(t):
        return {'winner':t['winner'],'number':t['number'],'cards':[{'seat':c['seat'],'card':c['card']} for c in t['cards']]}
    result['trick']=[{'seat':c['seat'],'card':c['card']} for c in s.get('trick',[])]
    result['last']=trick(s['last']) if s.get('last') else None
    result['history']=[trick(t) for t in s.get('history',[])[-5:]]
    return result


@require_GET
@never_cache
def watch(request,code):
    room=get_object_or_404(Room,code=code.upper())
    return render(request,'spectator.html',{'code':room.code})


@require_GET
@never_cache
def state(request,code):
    room=get_object_or_404(Room,code=code.upper())
    match=GroupMatch.objects.filter(room=room).first()
    can_join=not match or (request.user.is_authenticated and ConversationMember.objects.filter(conversation=match.conversation,user=request.user).exists())
    from .invitations import details
    invitation=details(room)
    return JsonResponse({'code':room.code,'state':snapshot(room),'invitation':invitation,'can_join':bool(can_join and invitation['open']),
                         'group_id':match.conversation_id if match and can_join else None})
