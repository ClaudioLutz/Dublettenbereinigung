
import unittest
import pandas as pd
import numpy as np
from duplicate_checker_optimized import MultiPassBlockingStrategy, UltraFastDuplicateChecker, get_cologne_phonetic

class TestMultiPassEnhancements(unittest.TestCase):

    def test_pass_b_key_generation(self):
        """Test Pass-B key generation is consistent and handles swaps"""
        strategy = MultiPassBlockingStrategy()

        # DataFrame with two records, names swapped, same year
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Meier'],
            'Name': ['Meier', 'Hans'],
            'Plz': ['12345', '12345'],
            'Strasse': ['', ''], # Missing street triggers street_only or something else?
            # Actually, to trigger Pass B we need:
            # pass_a_keys starts with plz_only_, street_only_, phon_, or no_address
            # AND effective_year present
            # If street is empty and PLZ present -> plz_only
            'Geburtstag': ['1980-01-01', '1980-01-01'],
            'Jahrgang': [1980, 1980]
        })

        keys_df = strategy.create_blocking_keys_vectorized(df)

        # Check Pass A keys
        pass_a = keys_df[keys_df['blocking_pass'] == 'A']
        self.assertEqual(len(pass_a), 2)
        # Should be plz_only_12345
        self.assertTrue(pass_a['blocking_key'].iloc[0].startswith('plz_only_'))

        # Check Pass B keys
        pass_b = keys_df[keys_df['blocking_pass'] == 'B']
        self.assertEqual(len(pass_b), 2)

        # Keys should be identical due to swap handling
        key1 = pass_b['blocking_key'].iloc[0]
        key2 = pass_b['blocking_key'].iloc[1]
        self.assertEqual(key1, key2)

        # Verify format: passB_{min}_{max}_{year}
        phon_hans = get_cologne_phonetic('Hans')
        phon_meier = get_cologne_phonetic('Meier')
        p_min = min(phon_hans, phon_meier)
        p_max = max(phon_hans, phon_meier)
        expected_key = f"passB_{p_min}_{p_max}_1980"
        self.assertEqual(key1, expected_key)

    def test_deduplication_across_passes(self):
        """Test that duplicate pairs found in both passes are deduplicated to highest confidence"""
        checker = UltraFastDuplicateChecker(use_multipass=True)

        # Setup matches that simulate finding the same pair in Pass A and Pass B
        # with different scores
        matches = [
            {
                'record_a_idx': 0, 'record_b_idx': 1,
                'confidence_score': 80.0, 'match_type': 'fuzzy',
                'details': {'blocking_pass': 'A'}
            },
            {
                'record_a_idx': 0, 'record_b_idx': 1,
                'confidence_score': 85.0, 'match_type': 'fuzzy',
                'details': {'blocking_pass': 'B'}
            },
            {
                'record_a_idx': 2, 'record_b_idx': 3,
                'confidence_score': 90.0, 'match_type': 'exact',
                'details': {'blocking_pass': 'A'}
            }
        ]

        deduped = checker._deduplicate_pairs(matches)

        self.assertEqual(len(deduped), 2)

        # Find pair (0, 1)
        pair_01 = next(m for m in deduped if m['record_a_idx'] == 0 and m['record_b_idx'] == 1)
        # Should keep the higher score (85 from Pass B)
        self.assertEqual(pair_01['confidence_score'], 85.0)
        self.assertEqual(pair_01['details']['blocking_pass'], 'B')

        # What if Pass A was higher?
        matches2 = [
            {
                'record_a_idx': 0, 'record_b_idx': 1,
                'confidence_score': 88.0, 'match_type': 'fuzzy',
                'details': {'blocking_pass': 'A'}
            },
            {
                'record_a_idx': 0, 'record_b_idx': 1,
                'confidence_score': 85.0, 'match_type': 'fuzzy',
                'details': {'blocking_pass': 'B'}
            }
        ]
        deduped2 = checker._deduplicate_pairs(matches2)
        self.assertEqual(len(deduped2), 1)
        self.assertEqual(deduped2[0]['confidence_score'], 88.0)
        self.assertEqual(deduped2[0]['details']['blocking_pass'], 'A')

    def test_street_only_sub_blocking_with_nans(self):
        """Test Issue 1: Ensure street_only sub-blocking handles NaNs in year without data loss"""
        strategy = MultiPassBlockingStrategy(max_block_size=2)

        df = pd.DataFrame({
            'Vorname': ['A', 'B', 'C', 'D'],
            'Name': ['X', 'X', 'X', 'X'],
            'Plz': ['', '', '', ''], # Empty PLZ -> street_only
            'Strasse': ['Main', 'Main', 'Main', 'Main'],
            'Geburtstag': ['2000', None, float('nan'), ''],
            'Jahrgang': [2000, None, float('nan'), '']
        })

        df.index = [0, 1, 2, 3] # Explicit

        blocks = strategy.create_blocks(df)

        total_records_in_blocks = sum(len(b) for b in blocks.values())

        # We expect 2 records (B and C) because:
        # A (Year 2000) is a singleton -> dropped
        # B, C, D (Year NaN) -> split into chunk [B, C] and [D]
        # [D] is a singleton -> dropped
        # So we expect exactly 2 records.
        # If NaN handling was broken, we would get 0 records.
        self.assertEqual(total_records_in_blocks, 2, "Should preserve NaN-year records (minus singletons)")

        # Verify specifically that B and C are in the blocks
        indices_in_blocks = []
        for b in blocks.values():
            indices_in_blocks.extend(b['index'].values)

        self.assertIn(1, indices_in_blocks) # B
        self.assertIn(2, indices_in_blocks) # C

    def test_sub_blocking_empty_names(self):
        """Test that sub-blocking handles empty names correctly"""
        strategy = MultiPassBlockingStrategy(max_block_size=2)

        # All same year (or no year) to force letter sub-blocking
        df = pd.DataFrame({
            'Vorname': ['A', 'B', 'C'],
            'Name': ['', '', ''], # Empty names
            'Plz': ['', '', ''],
            'Strasse': ['Main', 'Main', 'Main'],
            'Geburtstag': ['2000', '2000', '2000'],
            'Jahrgang': [2000, 2000, 2000]
        })

        blocks = strategy.create_blocks(df)
        # Should group all 3 into ..._L_EMPTY
        # Then chunked: [A, B], [C]
        # [C] dropped
        # So 2 records kept.

        total = sum(len(b) for b in blocks.values())
        self.assertEqual(total, 2)

        # Check key contains L_EMPTY
        keys = list(blocks.keys())
        self.assertTrue(any('L_EMPTY' in k for k in keys))

if __name__ == '__main__':
    unittest.main()
