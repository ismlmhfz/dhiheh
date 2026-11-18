"""Standalone Dutch state machine. No database, no 10 engine, explicit clock/RNG.

Only public() may cross the network boundary. Slot handles are independent of
card identities and survive swaps; discarded faces never carry hidden IDs.
"""
import copy
import secrets
from .dutch_rules import rules

ACTIVE={'initial_peek','playing','dutch_final'}
RESULTS={'round_results','match_results'}
RANKS=['A','2','3','4','5','6','7','8','9','10','J','Q','K']


def require(condition,message):
    if not condition: raise ValueError(message)


def new_state(n,identity,name,now,overrides=None):
    require(type(n) is int and 2<=n<=6,'Choose 2–6 seats.')
    return {'game_type':'dutch','schema_version':1,'rules':rules(overrides),
            'status':'lobby','phase':'lobby','host':0,'player_limit':n,
            'players':[{'id':identity,'name':name,'ready':False,'connected':False,'connections':{}}]+[None]*(n-1),
            'round':0,'max_rounds':10,'scores':[0]*n,'round_history':[],
            'hands':[[] for _ in range(n)],'cards':{},'draw_pile':[],'discard_pile':[],
            'peek_counts':[],'initial_peeks':{},'initial_peeks_done':[],
            'first_turn_done':[],'reserved':None,'jack_peeks':{},'cut_window':None,
            'dutch_caller':None,'final_turn_order':[],'final_turn_index':0,
            'turn':None,'starter':None,'turn_id':0,'event_counter':0,'event':None,
            'round_result':None,'winner_seats':[],'paused':False,'commands':[],
            'created_at':now,'revision':0,'invitation_closed':False}


def token(rng=None):
    return f'{(rng or secrets.SystemRandom()).getrandbits(128):032x}'


def event(s,kind,seat=None,**fields):
    s['event_counter']+=1
    s['event']={'id':s['event_counter'],'kind':kind,'seat':seat,**fields}


def counts(s,rng):
    r=s['rules'];v=rng.randint(r['peek_min'],r['peek_max'])
    return [v if r['shared_peek_count'] else rng.randint(r['peek_min'],r['peek_max']) for _ in s['players']]


def start(s,seat,now,rng=None):
    require(s['status']=='lobby' and seat==s['host'],'Only the host can start a lobby.')
    require(all(p and p['ready'] and p['connected'] for p in s['players']),'Fill every seat; everyone must be connected and ready.')
    rng=rng or secrets.SystemRandom()
    s.update(scores=[0]*s['player_limit'],round_history=[],round=0,peek_counts=counts(s,rng),winner_seats=[],invitation_closed=True)
    next_round(s,now,rng)


def next_round(s,now,rng=None):
    require(s['round']<10 and (s['round']==0 or s['status']=='round_results'),'There is no next round.')
    rng=rng or secrets.SystemRandom();n=s['player_limit'];s['round']+=1
    s['cards']={token(rng):{'rank':rank,'suit':suit} for suit in 'CDHS' for rank in RANKS}
    deck=list(s['cards']);rng.shuffle(deck)
    s['hands']=[[{'slot':token(rng),'card':deck.pop()} for _ in range(4)] for _ in range(n)]
    s['discard_pile']=[deck.pop()];s['draw_pile']=deck
    if s['rules']['reroll_peek_each_round']:s['peek_counts']=counts(s,rng)
    if s['starter'] is None or s['rules']['reroll_starter']:s['starter']=rng.randrange(n)
    s.update(status='initial_peek',phase='initial_peek',turn=s['starter'],
             initial_peeks={},initial_peeks_done=[False]*n,first_turn_done=[False]*n,
             initial_deadline=now+s['rules']['initial_select_seconds'],reserved=None,
             jack_peeks={},cut_window=None,dutch_caller=None,final_turn_order=[],
             final_turn_index=0,round_result=None,paused=False)
    s['turn_id']+=1;event(s,'round.started')


def next_seat(s,seat):return (seat+s['rules']['direction'])%s['player_limit']


def slot(s,seat,handle):
    return next((x for x in s['hands'][seat] if x['slot']==handle),None)


def own_slots(s,seat,handles):
    require(isinstance(handles,list) and handles and len(handles)<=52 and all(isinstance(h,str) for h in handles) and len(handles)==len(set(handles)),'Select distinct cards from your own hand.')
    selected=[slot(s,seat,h) for h in handles]
    require(all(selected),'A selected card is no longer in your hand.')
    return selected


def draw_card(s,rng=None):
    if not s['draw_pile'] and s['rules']['reshuffle_discards'] and len(s['discard_pile'])>1:
        s['draw_pile']=s['discard_pile'][:-1];s['discard_pile']=s['discard_pile'][-1:]
        (rng or secrets.SystemRandom()).shuffle(s['draw_pile'])
    require(bool(s['draw_pile']),'No draw cards are available. Take the discard or call Dutch when allowed.')
    return s['draw_pile'].pop()


def grant_jack(s,seat,card,now,cut=False):
    if s['cards'][card]['rank']!='J' or not s['hands'][seat] or s['status'] in RESULTS:return
    if cut and not s['rules']['jack_on_cut']:return
    if s['status']=='dutch_final' and not s['rules']['jack_in_final']:return
    # One grant per discard event; a new Jack replaces any previous grant.
    s['jack_peeks'][str(seat)]={'owner':s['players'][seat]['id'],'select_until':now+s['rules']['jack_select_seconds']}


def open_cut(s,now):
    if s['status']=='playing' and all(s['first_turn_done']):
        s['cut_window']={'event_id':token(),'expires_at':now+s['rules']['cut_seconds']}
        s['phase']='discard_resolving'
    else:s['cut_window']=None;s['phase']='normal_choice'


def finish(s,reason,actor):
    require(s['status'] in ('playing','dutch_final'),'This round is already finished.')
    totals=[sum(s['rules']['points'][s['cards'][x['card']]['rank']] for x in h) for h in s['hands']]
    earned=totals[:];success=True
    if reason=='dutch':
        opponents=[v for i,v in enumerate(totals) if i!=actor]
        success=totals[actor]<=min(opponents) if s['rules']['dutch_ties_win'] else totals[actor]<min(opponents)
        earned[actor]=0 if success else 2*totals[actor]
    else:earned[actor]=0
    s['scores']=[a+b for a,b in zip(s['scores'],earned)]
    result={'round':s['round'],'reason':reason,'actor':actor,'success':success,'totals':totals,'earned':earned,
            'scores':s['scores'][:],'hands':[[copy.deepcopy(s['cards'][x['card']]) for x in h] for h in s['hands']]}
    s['round_result']=result;s['round_history'].append(copy.deepcopy(result))
    s.update(status='match_results' if s['round']==10 else 'round_results',phase='results',turn=None,
             reserved=None,cut_window=None,jack_peeks={},initial_peeks={},paused=False)
    s['turn_id']+=1
    if s['round']==10:s['winner_seats']=[i for i,v in enumerate(s['scores']) if v==min(s['scores'])]
    event(s,'round.finished',actor,reason=reason)


def tick(s,now):
    if s['status'] not in ACTIVE:return
    for seat,p in list(s['initial_peeks'].items()):
        if now>=p['until']:s['initial_peeks_done'][int(seat)]=True;del s['initial_peeks'][seat]
    if s['status']=='initial_peek':
        if now>=s['initial_deadline']:
            for i in range(s['player_limit']):
                if str(i) not in s['initial_peeks']:s['initial_peeks_done'][i]=True
        if all(s['initial_peeks_done']):s['status']='playing';s['phase']='normal_choice';s['turn_id']+=1
    for seat,p in list(s['jack_peeks'].items()):
        if now>=p.get('until',p['select_until']):del s['jack_peeks'][seat]
    if s['reserved'] and now>=s['reserved']['until']:s['phase']='swap_select'
    if s['cut_window'] and now>=s['cut_window']['expires_at']:
        s['cut_window']=None;s['phase']='normal_choice';s['turn_id']+=1


def swap(s,seat,handle,incoming,now):
    target=slot(s,seat,handle);require(target is not None,'Choose one of your current card slots.')
    old=target['card'];target['card']=incoming;s['discard_pile'].append(old);s['reserved']=None
    s['first_turn_done'][seat]=True;s['turn_id']+=1
    event(s,'card.discarded',seat)
    if s['status']=='dutch_final':
        s['final_turn_index']+=1
        if s['final_turn_index']==len(s['final_turn_order']):finish(s,'dutch',s['dutch_caller']);return
        s['turn']=s['final_turn_order'][s['final_turn_index']];s['phase']='normal_choice'
    else:s['turn']=next_seat(s,seat);open_cut(s,now)
    grant_jack(s,seat,old,now)


def act(s,seat,action,data,now,rng=None):
    tick(s,now)
    require(type(seat) is int and 0<=seat<s['player_limit'] and s['players'][seat],'Join this table first.')
    require(not s['paused'],'Waiting for disconnected players to return.')
    if action=='initial_peek':
        require(s['status']=='initial_peek' and not s['initial_peeks_done'][seat] and str(seat) not in s['initial_peeks'],'Starting peek is no longer available.')
        selected=own_slots(s,seat,data.get('slots'))
        require(len(selected)==s['peek_counts'][seat],'Choose exactly your starting peek count.')
        s['initial_peeks'][str(seat)]={'owner':s['players'][seat]['id'],'cards':copy.deepcopy(selected),'until':now+s['rules']['initial_peek_seconds']}
        return
    require(s['status'] in ('playing','dutch_final'),'Wait for the current phase to finish.')
    if action=='jack_peek':
        grant=s['jack_peeks'].get(str(seat))
        require(grant and 'until' not in grant and grant['owner']==s['players'][seat]['id'] and now<grant['select_until'],'No Jack peek is available.')
        target=slot(s,seat,data.get('slot'));require(target is not None,'Choose one of your own cards.')
        grant.update(slot=target['slot'],card=target['card'],until=now+1)
        return
    if action=='cut':
        window=s['cut_window']
        require(s['status']=='playing' and all(s['first_turn_done']) and window and now<window['expires_at'] and data.get('event_id')==window['event_id'],'Cut window closed; no penalty was applied.')
        selected=own_slots(s,seat,data.get('slots'));rank=s['cards'][s['discard_pile'][-1]]['rank']
        matched=all(s['cards'][x['card']]['rank']==rank for x in selected)
        if not matched:
            require(s['rules']['atomic_bad_cut_penalty'],'That batch does not match; nothing was changed.')
            # Exhaustion fallback rejects before accepting the claim; no imaginary card.
            penalty=draw_card(s,rng)
            s['hands'][seat].append({'slot':token(rng),'card':penalty});s['cut_window']=None;s['phase']='normal_choice'
            if s['rules']['failed_cut_takes_turn']:s['turn']=seat
            s['turn_id']+=1;event(s,'cut.penalty',seat);return
        chosen={x['slot'] for x in selected};s['hands'][seat]=[x for x in s['hands'][seat] if x['slot'] not in chosen]
        s['discard_pile'].extend(x['card'] for x in selected);s['cut_window']=None;s['turn']=seat;s['turn_id']+=1
        event(s,'cut.accepted',seat,count=len(selected))
        if not s['hands'][seat]:finish(s,'empty_cut',seat);return
        s['phase']='normal_choice'
        if s['rules']['chain_cuts']:open_cut(s,now)
        grant_jack(s,seat,selected[-1]['card'],now,cut=True);return
    require(data.get('turn_id')==s['turn_id'],'Your table changed. Select the action again.')
    require(seat==s['turn'] or (action=='call' and not s['rules']['call_on_turn_only']),'It is not your turn.')
    if action=='swap_drawn':
        reserved=s['reserved'];require(reserved and reserved['owner']==s['players'][seat]['id'],'You have no drawn card to swap.')
        swap(s,seat,data.get('slot'),reserved['card'],now);return
    require(s['phase']=='normal_choice' and s['reserved'] is None and s['cut_window'] is None,'Finish the pending action or cut window first.')
    if action=='call':
        require(s['status']=='playing' and all(s['first_turn_done']) and not s['jack_peeks'],'Dutch is locked until everyone has played and peeks are resolved.')
        order=[];i=next_seat(s,seat)
        while i!=seat:order.append(i);i=next_seat(s,i)
        s.update(status='dutch_final',dutch_caller=seat,final_turn_order=order,final_turn_index=0,turn=order[0])
        s['turn_id']+=1;event(s,'dutch.called',seat);return
    if action=='draw':
        card=draw_card(s,rng);s['reserved']={'owner':s['players'][seat]['id'],'seat':seat,'card':card,'until':now+2}
        s['phase']='draw_reveal';s['turn_id']+=1;return
    if action=='take_discard':
        require(slot(s,seat,data.get('slot')) is not None,'Choose one of your own cards.')
        require(bool(s['discard_pile']),'The discard pile is empty.')
        incoming=s['discard_pile'].pop();swap(s,seat,data['slot'],incoming,now);return
    raise ValueError('Unknown Dutch action.')


def public(s,viewer,now):
    """Allowlisted projection; reveal access is checked even without a timer tick."""
    r=s['rules'];playing=s['status'] in ('playing','dutch_final');own=viewer is not None
    window=s['cut_window'] if s['cut_window'] and now<s['cut_window']['expires_at'] else None
    result={k:copy.deepcopy(s[k]) for k in ('game_type','status','phase','player_limit','host','round','max_rounds','scores','turn','turn_id','starter','dutch_caller','final_turn_order','final_turn_index','round_result','round_history','winner_seats','paused','revision','event')}
    result.update(server_now=now,seat=viewer,rules=copy.deepcopy(r),
                  players=[{k:p.get(k) for k in ('name','avatar','ready','connected')} if p else None for p in s['players']],
                  counts=[len(h) for h in s['hands']],draw_count=len(s['draw_pile']),
                  can_draw=bool(s['draw_pile'] or (r['reshuffle_discards'] and len(s['discard_pile'])>1)),
                  discard=copy.deepcopy(s['cards'][s['discard_pile'][-1]]) if s['discard_pile'] else None,
                  cut_window=copy.deepcopy(window),unlocked=bool(s['first_turn_done'] and all(s['first_turn_done'])),
                  can_call=bool(own and s['status']=='playing' and all(s['first_turn_done']) and s['phase']=='normal_choice' and not s['jack_peeks'] and not s['reserved'] and not window and (viewer==s['turn'] or not r['call_on_turn_only']) and not s['paused']),
                  slots=[x['slot'] for x in s['hands'][viewer]] if own else [],reveals={},drawn=None,jack=None,
                  peek_count=s['peek_counts'][viewer] if own and s['peek_counts'] else 0,
                  initial_selected=bool(own and (s['initial_peeks_done'] and s['initial_peeks_done'][viewer] or str(viewer) in s['initial_peeks'])),
                  initial_deadline=s.get('initial_deadline') if s['status']=='initial_peek' else None)
    if own and s['status'] in ACTIVE:
        identity=s['players'][viewer]['id']
        peek=s['initial_peeks'].get(str(viewer))
        if peek and peek['owner']==identity and now<peek['until']:
            for x in peek['cards']:result['reveals'][x['slot']]={'face':copy.deepcopy(s['cards'][x['card']]),'until':peek['until']}
        peek=s['jack_peeks'].get(str(viewer))
        if peek and peek['owner']==identity and now<peek.get('until',peek['select_until']):
            result['jack']={'choose':'until' not in peek,'until':peek.get('until',peek['select_until'])}
            current=slot(s,viewer,peek.get('slot'))
            if 'until' in peek and current and current['card']==peek['card']:
                result['reveals'][current['slot']]={'face':copy.deepcopy(s['cards'][peek['card']]),'until':peek['until']}
        held=s['reserved']
        if held and held['owner']==identity:
            result['drawn']={'until':held['until'],'face':copy.deepcopy(s['cards'][held['card']]) if now<held['until'] else None}
    return result
