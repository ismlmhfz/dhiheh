import os
from pathlib import Path
import dj_database_url
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY', 'local-development-only-ten-card-game')
DEBUG = os.environ.get('TEN_DEBUG', '1').lower() in ('1','true','yes')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['daphne','django.contrib.admin','django.contrib.messages','django.contrib.contenttypes','django.contrib.auth','django.contrib.sessions','django.contrib.staticfiles','game']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware']
ROOT_URLCONF = 'ten.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
DATABASES = {'default':dj_database_url.config(default='sqlite:///'+str(BASE_DIR/'db.sqlite3'))}
if DATABASES['default']['ENGINE']=='django.db.backends.sqlite3':
    DATABASES['default']['OPTIONS']={'timeout':20,'transaction_mode':'IMMEDIATE'}
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR/'static']
ASGI_APPLICATION = 'ten.asgi.application'
CHANNEL_LAYERS = {'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}}
if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {'default':{'BACKEND':'channels_redis.core.RedisChannelLayer','CONFIG':{'hosts':[{'address':os.environ['REDIS_URL'],'socket_timeout':None,'socket_connect_timeout':5}]}}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
CARD_RANKS = os.environ.get('CARD_RANKS','2,3,4,5,6,7,8,9,10,J,Q,K,A').split(',')
CHASE_TIMEOUT = int(os.environ.get('CHASE_TIMEOUT','15'))
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND','django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST','localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT','587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS','1') == '1'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL','Card Club <noreply@localhost>')
# Configure a credentialed TURN server for reliable voice across networks.
VOICE_ICE_SERVERS = [{'urls':['stun:stun.l.google.com:19302']}]
if os.environ.get('TURN_URL'):
    VOICE_ICE_SERVERS.append({'urls':os.environ['TURN_URL'].split(','),'username':os.environ.get('TURN_USERNAME',''),'credential':os.environ.get('TURN_PASSWORD','')})

# Reject cross-game routes before the original 10 views are invoked.
MIDDLEWARE += ['game.dutch_views.TenIsolationMiddleware']
