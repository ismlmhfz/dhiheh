"""Join invitations expire independently of seated-player and spectator access."""
from datetime import timedelta
from django.utils import timezone

def details(room):
    expires=room.created_at+timedelta(hours=1)
    s=room.state
    full=s.get('invitation_closed',False) or all(s.get('players',[None]*4))
    reason='Table filled' if full else 'Invitation expired' if timezone.now()>=expires else 'Match started' if s['status']!='lobby' else ''
    return {'open':not bool(reason),'reason':reason,'expires_at':expires.isoformat()}
