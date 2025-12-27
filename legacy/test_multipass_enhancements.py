
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
            'Strasse': ['', ''],
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
        """Test that duplicate pairs found in both passes are deduplicated to highest confidence and provenances matched"""
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
        # Should have both passes in blocking_passes
        self.assertEqual(sorted(pair_01['details']['blocking_passes']), ['A', 'B'])

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
        self.assertEqual(sorted(deduped2[0]['details']['blocking_passes']), ['A', 'B'])

if __name__ == '__main__':
    unittest.main()
