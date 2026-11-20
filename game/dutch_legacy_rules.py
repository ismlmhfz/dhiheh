"""Dutch engineering defaults, NOT additional owner-confirmed rules.

Override with settings.DUTCH_RULES. Each room freezes a copy at creation.
Required rules (2s draw, 1s Jack, 10 rounds, no final cuts) are not switches.
"""
from copy import deepcopy

DUTCH_RULES = {
    'points': {r: i for i, r in enumerate(['A','2','3','4','5','6','7','8','9','10','J','Q','K'], 1)},
    'peek_min': 1, 'peek_max': 4, 'shared_peek_count': True,
    'reroll_peek_each_round': False, 'initial_peek_seconds': 3,
    'initial_select_seconds': 30,  # timeout forfeits unselected peeks; never reveals automatically
    'direction': 1, 'call_on_turn_only': True, 'dutch_ties_win': True,
    'atomic_bad_cut_penalty': True,  # False rejects a mixed/wrong batch without accepting the claim
    'failed_cut_takes_turn': True, 'cut_seconds': 3, 'chain_cuts': True,
    'jack_on_cut': True, 'jack_in_final': True, 'jack_select_seconds': 10,
    'reshuffle_discards': True, 'empty_penalty': 'reject',
    'reroll_starter': True, 'disconnect_grace_seconds': 90,
}


def rules(overrides=None):
    result=deepcopy(DUTCH_RULES)
    if overrides:
        if set(overrides)-set(result): raise ValueError('Unknown Dutch rule setting.')
        result.update(deepcopy(overrides))
    if set(result['points'])!=set(DUTCH_RULES['points']) or any(type(v) is not int or v<0 for v in result['points'].values()):
        raise ValueError('Provide nonnegative integer values for all 13 ranks.')
    for key,default in DUTCH_RULES.items():
        if isinstance(default,bool) and type(result[key]) is not bool:raise ValueError('Dutch switches must be booleans.')
    if any(type(result[k]) is not int for k in ('peek_min','peek_max','direction')):raise ValueError('Peek counts and direction must be integers.')
    if not 1<=result['peek_min']<=result['peek_max']<=4 or result['direction'] not in (-1,1):
        raise ValueError('Invalid Dutch peek count or direction.')
    for k in ('initial_peek_seconds','initial_select_seconds','cut_seconds','jack_select_seconds','disconnect_grace_seconds'):
        if not isinstance(result[k],(int,float)) or not 0<result[k]<=300: raise ValueError('Invalid Dutch duration.')
    if result['empty_penalty']!='reject': raise ValueError('Only the safe reject fallback is supported for an unavailable penalty.')
    return result
