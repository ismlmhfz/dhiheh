"""Pure server-owned game rules. JSON state is persisted atomically per room."""
import secrets, time
from django.conf import settings
SUITS = 'SHDC'
MODES = {'quick':(8,5),'standard':(12,7),'long':(18,11)}
def next_turn(trick):
    seat=(trick[-1]['seat']-1)%4
    played={x['seat'] for x in trick}
    while len(played)<4 and seat in played: seat=(seat-1)%4
    return seat
def legal(hand, lead=None):
    matching = [c for c in hand if c[-1] == lead]
    return matching or hand
def points(tens, stacks):
    return 5 if tens == 4 else 3 if tens >= 3 else 2 if tens >= 2 and stacks >= 7 else 0
def new_match(s):
    s.update(status='playing',paused=False,lead_rule='winner',scores=[0,0],totals_tens=[0,0],totals_stacks=[0,0],deal=0,history=[],winner=None)
    new_deal(s)
def new_deal(s):
    deck = [r+su for su in SUITS for r in settings.CARD_RANKS]
    secrets.SystemRandom().shuffle(deck)
    s.update(deal=s['deal']+1,hands=[sorted(deck[i*13:(i+1)*13],key=lambda c:(SUITS.index(c[-1]),settings.CARD_RANKS.index(c[:-1]))) for i in range(4)],trump=None,stacks=[0,0],tens=[[],[]],trick=[],last=None,chase=None,decision=None,status='playing',history=[])
    s['designated'] = secrets.randbelow(4)
    s['starter'] = s['turn'] = s['designated']
def finish(s,team,reward):
    s['scores'][team] += reward
    for t in range(2):
        s['totals_tens'][t] += len(s['tens'][t]); s['totals_stacks'][t] += s['stacks'][t]
    s['result'] = {'team':team,'points':reward}
    target,limit = MODES[s['mode']]
    s['status'] = 'deal_results'
    if max(s['scores']) >= target or s['deal'] >= limit:
        a,b = [(s['scores'][t],s['totals_tens'][t],s['totals_stacks'][t]) for t in range(2)]
        s['winner'] = 0 if a>b else 1 if b>a else None
        s['status'] = 'match_results'
def play(s,seat,card):
    if s['status'] != 'playing' or s.get('paused'): raise ValueError('The table is not ready for a move.')
    if seat != s['turn']: raise ValueError('Wait for your turn.')
    hand = s['hands'][seat]
    lead = s['trick'][0]['card'][-1] if s['trick'] else None
    if card not in hand: raise ValueError('That card is not in your hand.')
    if card not in legal(hand,lead): raise ValueError('You must follow the lead suit.')
    if lead and card[-1] != lead and not s['trump']: s['trump'] = card[-1]
    hand.remove(card); s['trick'].append({'seat':seat,'card':card})
    s['turn'] = next_turn(s['trick'])
    if len(s['trick']) < 4: return
    winning_suit = s['trump'] if any(x['card'][-1]==s['trump'] for x in s['trick']) else lead
    winner = max((x for x in s['trick'] if x['card'][-1]==winning_suit),key=lambda x:settings.CARD_RANKS.index(x['card'][:-1]))['seat']
    team = winner%2
    s['stacks'][team] += 1
    s['tens'][team] += [x['card'][-1] for x in s['trick'] if x['card'][:-1]=='10']
    s['last'] = {'cards':s['trick'],'winner':winner,'number':sum(s['stacks'])}
    s['history'].append(s['last']); s['trick'] = []
    s['starter'] = s['turn'] = winner
    if s['chase']:
        t = s['chase']['team']
        if len(s['tens'][t])==4: finish(s,t,5)
        elif s['tens'][1-t] or sum(s['stacks'])==13: finish(s,t,s['chase']['locked'])
        return
    reward = points(len(s['tens'][team]),s['stacks'][team])
    if reward:
        if reward<5 and not s['tens'][1-team] and sum(s['stacks'])<13:
            s.update(status='chase_decision',decision={'seat':winner,'team':team,'points':reward,'deadline':time.time()+settings.CHASE_TIMEOUT})
        else: finish(s,team,reward)
def decide(s,chase):
    d = s['decision']
    if chase:
        s.update(chase={'team':d['team'],'locked':d['points']},decision=None,status='playing')
    else:
        finish(s,d['team'],d['points']); s['decision']=None
def tick(s):
    now = time.time()
    if s.get('paused'):
        if any(p and p.get('disconnected_at') and now-p['disconnected_at']>=90 for p in s['players']):
            s.update(status='abandoned',paused=False)
    elif s.get('decision') and now >= s['decision']['deadline']: decide(s,False)
def public(s,seat):
    result = {k:v for k,v in s.items() if k not in ('hands','players','commands','creator')}
    result['players'] = [{k:v for k,v in p.items() if k not in ('id','connections','voice_owner')} if p else None for p in s['players']]
    result['seat'] = seat
    result['counts'] = [len(h) for h in s.get('hands',[[],[],[],[]])]
    result['hand'] = s.get('hands',[[],[],[],[]])[seat]
    lead = s['trick'][0]['card'][-1] if s.get('trick') else None
    result['legal'] = legal(result['hand'],lead) if s['status']=='playing' and s['turn']==seat and not s.get('paused') else []
    return result
