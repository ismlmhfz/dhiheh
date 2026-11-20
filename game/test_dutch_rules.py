from django.test import SimpleTestCase
from .dutch_rules import rules, DUTCH_RULES, RANKS


class DutchRulesTests(SimpleTestCase):
    def test_defaults_validate(self):
        r = rules()
        self.assertEqual(r['card_values'], {x: i for i, x in enumerate(RANKS, 1)})
        self.assertEqual((r['reveal_min'], r['reveal_max']), (0, 4))
        self.assertEqual(r['turn_seconds'], 30)
        self.assertEqual(r['draw_preview_seconds'], 3)
        self.assertFalse(r['dutch_tie_counts_as_win'])
        self.assertFalse(r['failed_cutter_takes_next_turn'])
        self.assertFalse(r['pause_on_disconnect'])
        self.assertTrue(r['abandon_when_all_idle'])
        self.assertEqual(r['powers'], {'jack': True, 'queen': True, 'king': True})

    def test_returns_independent_frozen_copy(self):
        r = rules()
        r['turn_seconds'] = 999
        r['powers']['jack'] = False
        self.assertEqual(DUTCH_RULES['turn_seconds'], 30)
        self.assertTrue(DUTCH_RULES['powers']['jack'])

    def test_valid_overrides_apply(self):
        r = rules({'turn_seconds': 20, 'dutch_tie_counts_as_win': True,
                   'reveal_min': 1, 'reveal_max': 2, 'powers': {'jack': True, 'queen': False, 'king': False}})
        self.assertEqual(r['turn_seconds'], 20)
        self.assertTrue(r['dutch_tie_counts_as_win'])
        self.assertEqual((r['reveal_min'], r['reveal_max']), (1, 2))
        self.assertFalse(r['powers']['queen'])

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            rules({'nonsense': 1})

    def test_card_values_must_cover_13_ranks(self):
        with self.assertRaises(ValueError):
            rules({'card_values': {'A': 1}})
        with self.assertRaises(ValueError):
            rules({'card_values': {r: (-1 if r == 'K' else i) for i, r in enumerate(RANKS, 1)}})

    def test_boolean_switch_type_enforced(self):
        with self.assertRaises(ValueError):
            rules({'allow_discard_drawn': 'yes'})

    def test_powers_shape_enforced(self):
        with self.assertRaises(ValueError):
            rules({'powers': {'jack': True}})
        with self.assertRaises(ValueError):
            rules({'powers': {'jack': 1, 'queen': True, 'king': True}})

    def test_reveal_range_and_direction(self):
        with self.assertRaises(ValueError):
            rules({'reveal_min': 3, 'reveal_max': 2})
        with self.assertRaises(ValueError):
            rules({'reveal_max': 5})
        with self.assertRaises(ValueError):
            rules({'direction': 0})

    def test_durations_bounded(self):
        with self.assertRaises(ValueError):
            rules({'turn_seconds': 0})
        with self.assertRaises(ValueError):
            rules({'turn_seconds': 301})
        with self.assertRaises(ValueError):
            rules({'jack_peek_seconds': True})  # bool is not a valid duration

    def test_counts_bounded(self):
        with self.assertRaises(ValueError):
            rules({'rounds': 0})
        with self.assertRaises(ValueError):
            rules({'failed_dutch_multiplier': 0})
        with self.assertRaises(ValueError):
            rules({'failed_cut_penalty_cards': -1})

    def test_enums_restricted(self):
        with self.assertRaises(ValueError):
            rules({'king_target': 'enemies'})
        with self.assertRaises(ValueError):
            rules({'empty_draw_pile': 'discard'})
        self.assertEqual(rules({'king_target': 'own'})['king_target'], 'own')
