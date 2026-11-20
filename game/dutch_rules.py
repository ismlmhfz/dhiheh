"""The single configurable Dutch rule object.

`RULES_DUTCH.md` is the source of truth; this mirrors its Configuration table.
Override with settings.DUTCH_RULES. Each room freezes a copy at creation.
Every value here is configurable — the new ruleset has no hard-coded invariants —
but confirmed values should not be changed casually. Keys that still await owner
confirmation are grouped under "defaults (confirm)" below.
"""
from copy import deepcopy

RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

DUTCH_RULES = {
    # --- confirmed ---
    'card_values': {r: v for v, r in enumerate(RANKS, 1)},  # A=1 .. K=13
    'use_jokers': False,
    'reveal_min': 0, 'reveal_max': 4,          # rotating chooser picks in [min, max]
    'direction': 1,                            # turn + chooser rotation ("right")
    'starting_peek_seconds': 3,
    'draw_preview_seconds': 3,
    'turn_seconds': 30,
    'allow_discard_drawn': True,
    'powers': {'jack': True, 'queen': True, 'king': True},  # drawn-and-discarded-straight-away
    'jack_peek_seconds': 1,
    'cut_opponent_cards': False,               # own cards only
    'cutter_takes_next_turn': True,
    'failed_cut_penalty_cards': 1,
    'cuts_are_public': True,                   # cut card and result shown to all
    'empty_hand_ends_round': True,             # cutter scores 0
    'cut_during_dutch_final': False,
    'dutch_tie_counts_as_win': False,          # a tie FAILS the call
    'failed_dutch_multiplier': 2,
    'rounds': 10,                              # no early score cut-off
    'reconnect_full_resume': True,
    'replaced_slot_is_public': True,

    # --- defaults (confirm) ---
    'first_player': 'chooser',                 # 'chooser' | 'random'
    'setup_choice_seconds': 10,                # chooser pick window, then the shared select window
    'timeout_before_draw': 'skip',             # only 'skip' supported
    'timeout_after_draw': 'auto_discard',      # only 'auto_discard' (no power) supported
    'king_target': 'any',                      # 'any' | 'own'
    'unlocked_card_face_down': True,
    'cut_locked_card': 'blocked',              # only 'blocked' (no penalty) supported
    'multi_card_cut': False,
    'cut_on_cut_card': True,
    'failed_cutter_takes_next_turn': False,
    'failed_cut_reveal_seconds': 2,
    'match_tie': 'joint',                      # only 'joint' supported
    'empty_draw_pile': 'reshuffle',            # only 'reshuffle' (except top) supported
    'pause_on_disconnect': False,
    'abandon_when_all_idle': True,             # safeguard: no seat connected a full turn -> abandon round
}

_DURATIONS = ('starting_peek_seconds', 'draw_preview_seconds', 'turn_seconds',
              'jack_peek_seconds', 'setup_choice_seconds', 'failed_cut_reveal_seconds')
_ENUMS = {'first_player': {'chooser', 'random'}, 'timeout_before_draw': {'skip'},
          'timeout_after_draw': {'auto_discard'}, 'king_target': {'any', 'own'},
          'cut_locked_card': {'blocked'}, 'match_tie': {'joint'},
          'empty_draw_pile': {'reshuffle'}}


def rules(overrides=None):
    result = deepcopy(DUTCH_RULES)
    if overrides:
        if set(overrides) - set(result): raise ValueError('Unknown Dutch rule setting.')
        for k, v in overrides.items():
            result[k] = deepcopy(v) if isinstance(result[k], (dict,)) and isinstance(v, dict) else v
    # card values: exactly the 13 ranks, nonnegative integers
    if set(result['card_values']) != set(RANKS) or any(type(v) is not int or v < 0 for v in result['card_values'].values()):
        raise ValueError('Provide nonnegative integer values for all 13 ranks.')
    # boolean switches
    for key, default in DUTCH_RULES.items():
        if isinstance(default, bool) and type(result[key]) is not bool:
            raise ValueError('Dutch switches must be booleans.')
    if not isinstance(result['powers'], dict) or set(result['powers']) != {'jack', 'queen', 'king'} \
            or any(type(v) is not bool for v in result['powers'].values()):
        raise ValueError('Dutch powers must be jack/queen/king booleans.')
    # reveal range + direction
    if any(type(result[k]) is not int for k in ('reveal_min', 'reveal_max', 'direction', 'rounds', 'failed_cut_penalty_cards', 'failed_dutch_multiplier')):
        raise ValueError('Dutch counts must be integers.')
    if not 0 <= result['reveal_min'] <= result['reveal_max'] <= 4 or result['direction'] not in (-1, 1):
        raise ValueError('Invalid Dutch reveal range or direction.')
    if not 1 <= result['rounds'] <= 100 or result['failed_cut_penalty_cards'] < 0 or result['failed_dutch_multiplier'] < 1:
        raise ValueError('Invalid Dutch round, penalty or multiplier count.')
    # durations
    for k in _DURATIONS:
        if not isinstance(result[k], (int, float)) or isinstance(result[k], bool) or not 0 < result[k] <= 300:
            raise ValueError('Invalid Dutch duration.')
    # enumerations (only safe/supported values accepted)
    for k, allowed in _ENUMS.items():
        if result[k] not in allowed: raise ValueError(f'Unsupported value for Dutch setting {k}.')
    return result
