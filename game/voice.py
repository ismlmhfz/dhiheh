import base64, hashlib, hmac, os, time
from django.conf import settings

def configuration(identity):
    servers=list(settings.VOICE_ICE_SERVERS)
    secret=os.environ.get('TURN_SHARED_SECRET')
    if secret:
        username=f'{int(time.time())+86400}:{hashlib.sha256(identity.encode()).hexdigest()[:16]}'
        credential=base64.b64encode(hmac.new(secret.encode(),username.encode(),hashlib.sha1).digest()).decode()
        servers.append({'urls':os.environ['TURN_RELAY_URLS'].split(','),'username':username,'credential':credential})
    return {'iceServers':servers}
