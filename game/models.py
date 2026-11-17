from django.db import models
from django.conf import settings
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    nickname = models.CharField(max_length=24)
    avatar = models.CharField(max_length=20,default='fox')
    deck = models.CharField(max_length=20,default='cosmic')
class Room(models.Model):
    code = models.CharField(max_length=6,unique=True)
    state = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=128)
    name = models.CharField(max_length=24)
    text = models.CharField(max_length=500)
    command = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['room', 'sender', 'command'], name='unique_room_chat_command')]
        ordering = ['id']

class Friendship(models.Model):
    first = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendships_first')
    second = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendships_second')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friend_requests_sent')
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['first','second'], name='unique_friend_pair')]

class Conversation(models.Model):
    kind = models.CharField(max_length=8, choices=[('direct','Direct'),('group','Group')])
    title = models.CharField(max_length=48, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_chats')
    direct_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

class ConversationMember(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_memberships')
    last_read_id = models.BigIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation','user'], name='unique_chat_member')]

class GroupMatch(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='group_match')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='matches')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ConversationMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.CharField(max_length=1000, blank=True)
    command = models.CharField(max_length=64)
    match = models.ForeignKey(GroupMatch, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['conversation','sender','command'], name='unique_social_message')]
