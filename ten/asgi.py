import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','ten.settings')
from django.core.asgi import get_asgi_application
django_application = get_asgi_application()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import re_path
from game.consumer import RoomConsumer
application = ProtocolTypeRouter({'http':django_application,'websocket':AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter([re_path(r'ws/room/(?P<code>[A-Z0-9]{6})/$',RoomConsumer.as_asgi())])))})
