from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Room, ChatMessage
from .service import seat_of


def public(message):
    return {'id': message.id, 'name': message.name, 'text': message.text,
            'time': message.created_at.isoformat()}


def member(room, identity):
    seat = seat_of(room.state, identity)
    if seat is None:
        raise ValueError('Join this room to use chat.')
    return room.state['players'][seat]


def history(code, identity):
    room = Room.objects.get(code=code)
    member(room, identity)
    return [public(m) for m in reversed(list(room.messages.order_by('-id')[:100]))]


@transaction.atomic
def post(code, identity, text, command):
    room = Room.objects.select_for_update().get(code=code)
    player = member(room, identity)
    if not isinstance(text, str) or not text.strip() or len(text) > 120:
        raise ValueError('Write a message between 1 and 120 characters.')
    if not isinstance(command, str) or not command or len(command) > 64:
        raise ValueError('Invalid message identifier.')
    existing = room.messages.filter(sender=identity, command=command).first()
    if existing:
        return {**public(existing),'seat':seat_of(room.state,identity),'revision':room.state.get('seating_revision',0)}
    if room.messages.filter(sender=identity, created_at__gte=timezone.now()-timedelta(seconds=10)).count() >= 5:
        raise ValueError('Please wait a few seconds before sending more messages.')
    message = ChatMessage.objects.create(room=room, sender=identity,
        name=player['name'], text=text.strip(), command=command)
    keep = list(room.messages.order_by('-id').values_list('id', flat=True)[:100])
    room.messages.exclude(id__in=keep).delete()
    return {**public(message),'seat':seat_of(room.state,identity),'revision':room.state.get('seating_revision',0)}
