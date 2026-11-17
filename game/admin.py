"""Operations dashboard; live hands, session identities and private messages stay out of admin."""
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.db.models import Count
from django.utils.html import format_html
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Profile, Room, Conversation, ConversationMember, ConversationMessage, GroupMatch
from .invitations import details

admin.site.site_header='10 Card Party administration'
admin.site.site_title='Card Party admin'
admin.site.index_title='Manage the club'

class ProfileInline(admin.StackedInline):
    model=Profile
    extra=0

User=get_user_model()
admin.site.unregister(User)
@admin.register(User)
class PlayerAdmin(UserAdmin):
    inlines=[ProfileInline]
    list_display=('username','email','is_active','is_staff','date_joined','last_login')
    list_filter=('is_active','is_staff','is_superuser','date_joined')

class StatusFilter(admin.SimpleListFilter):
    title='table status'
    parameter_name='status'
    def lookups(self,request,model_admin):
        return [(s,s.replace('_',' ').title()) for s in ('lobby','playing','chase_decision','deal_results','match_results','abandoned')]
    def queryset(self,request,queryset):
        return queryset.filter(state__status=self.value()) if self.value() else queryset

@admin.register(Room)
class TableAdmin(admin.ModelAdmin):
    list_display=('code','table_status','players','invite_status','created_at')
    list_filter=(StatusFilter,'created_at')
    search_fields=('code',)
    readonly_fields=('code','table_status','players','invite_status','created_at','watch_link')
    fields=readonly_fields
    actions=['close_invitations']
    def has_add_permission(self,request): return False
    @admin.display(description='Status')
    def table_status(self,obj): return obj.state.get('status','').replace('_',' ').title()
    @admin.display(description='Players')
    def players(self,obj): return ', '.join(p['name'] for p in obj.state.get('players',[]) if p) or 'Empty'
    @admin.display(description='Invitation')
    def invite_status(self,obj):
        info=details(obj)
        return 'Open until '+info['expires_at'] if info['open'] else info['reason']
    def watch_link(self,obj): return format_html('<a href="/watch/{}/" target="_blank" rel="noopener">Watch public table</a>',obj.code)
    @admin.action(description='Close invitations for selected tables')
    def close_invitations(self,request,queryset):
        with transaction.atomic():
            for room in queryset.select_for_update():
                room.state['invitation_closed']=True;room.save(update_fields=['state'])
                self.log_change(request,room,'Closed invitation')
        self.message_user(request,'Invitations closed. Seated players can still reconnect.')
    def delete_model(self,request,obj):
        ConversationMessage.objects.filter(match__room=obj).update(text='This table was removed by an administrator.')
        code=obj.code
        obj.delete()
        transaction.on_commit(lambda:async_to_sync(get_channel_layer().group_send)('room_'+code,{'type':'table_deleted'}))
    def delete_queryset(self,request,queryset):
        for room in queryset:self.delete_model(request,room)

class MemberInline(admin.TabularInline):
    model=ConversationMember
    extra=0
    fields=('user','joined_at')
    readonly_fields=fields
    def has_add_permission(self,request,obj=None):return False

@admin.register(Conversation)
class GroupAdmin(admin.ModelAdmin):
    list_display=('title','owner','member_count','created_at')
    search_fields=('title','owner__username')
    fields=('title','owner','created_at')
    readonly_fields=('created_at',)
    autocomplete_fields=('owner',)
    inlines=[MemberInline]
    def get_queryset(self,request):return super().get_queryset(request).filter(kind='group').annotate(members_total=Count('members'))
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False
    @admin.display(description='Members')
    def member_count(self,obj):return obj.members_total

@admin.register(LogEntry)
class AuditAdmin(admin.ModelAdmin):
    list_display=('action_time','user','content_type','object_repr','action_flag')
    list_filter=('action_flag','content_type','action_time')
    search_fields=('object_repr','user__username')
    readonly_fields=('action_time','user','content_type','object_id','object_repr','action_flag','change_message')
    fields=readonly_fields
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
