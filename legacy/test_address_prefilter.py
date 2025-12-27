
import unittest
import pandas as pd
from duplicate_checker_optimized import UltraFastDuplicateChecker

class TestAddressPrefilter(unittest.TestCase):

    def test_address_assisted_match(self):
        """Test that weak name match + strong address match yields address_assisted_match"""
        checker = UltraFastDuplicateChecker(enable_address_aware=True, fuzzy_threshold=0.85)

        # We need a pair:
        # 1. Fuzzy score in [0.60, 0.85).
        # 2. Phonetic code different (to avoid phonetic fallback).
        # 3. Address match strong.

        # Tanja (26) vs Sonja (86). QRatio 60.0.
        # This is exactly 0.60.

        df = pd.DataFrame({
            'Vorname': ['Tanja', 'Sonja'],
            'Name': ['Müller', 'Müller'], # Names match exactly? If so, Name similarity will be high!
            # Ah, `compare_names` compares (v_a, n_a) vs (v_b, n_b).
            # If Name is identical, score will be boosted.
            # QRatio('Tanja', 'Sonja') = 60.
            # QRatio('Müller', 'Müller') = 100.
            # Avg = 80.
            # 80 < 85? Yes.
            # Phonetic: Müller (657) == Müller (657).
            # Phonetic match will be found on surname!
            # Wait, phonetic match requires BOTH Vorname AND Name to match phonetically.
            # v_a_phon == v_b_phon AND n_a_phon == n_b_phon.
            # Tanja (26) != Sonja (86).
            # So phonetic match fails.

            # So Avg Score = 80.
            # 80 is in [60, 85).
            # Address match: Strong.

            # So this should work!

            'Strasse': ['Musterweg 1', 'Musterweg 1'],
            'Plz': ['12345', '12345'],
            'Ort': ['Berlin', 'Berlin'],
            'Geburtstag': ['1980-01-01', '1980-01-01'],
            'Jahrgang': [1980, 1980]
        })

        matches = checker.analyze_duplicates(df, confidence_threshold=70.0)

        self.assertEqual(len(matches), 1)
        m = matches[0]
        self.assertEqual(m.match_type, 'address_assisted_normal')

    def test_address_assisted_disabled(self):
        """Test that disabling the feature prevents the match"""
        checker = UltraFastDuplicateChecker(enable_address_aware=False, fuzzy_threshold=0.85)

        # Same data as above.
        # Score = 80.
        # Address aware disabled -> skipped.
        # Phonetic match? Tanja != Sonja. Fails.
        # Fallthrough to standard fuzzy.
        # Base confidence = 80 * 0.5 = 40.
        # Address bonus = 30.
        # Total = 70.
        # 70 >= 70.
        # IT WILL MATCH as fuzzy_normal!

        # I need the score to be such that standard fuzzy < 70.
        # Score * 0.5 + 30 < 70 => Score * 0.5 < 40 => Score < 80.

        # So I need score in [60, 80).
        # Tanja/Sonja (60) + Muller/Muller (100) = 80.
        # I need slightly different surnames too.
        # Müller vs Müllar?
        # QRatio('Müller', 'Müllar')? ~83.
        # (60 + 83)/2 = 71.5.
        # 71.5 * 0.5 = 35.75.
        # 35.75 + 30 = 65.75 < 70.
        # Perfect.

        # But wait, 71.5 is in [60, 85).
        # And phonetics?
        # Tanja != Sonja.
        # Müller (657) == Müllar (657).
        # Phonetic match fails (requires both).

        # So:
        # Enabled: Address check -> Matches (address strong).
        # Disabled: Skip address -> Phonetic fails -> Standard fuzzy (65.75) -> Fails.

        df = pd.DataFrame({
            'Vorname': ['Tanja', 'Sonja'],
            'Name': ['Müller', 'Müllar'],
            'Strasse': ['Musterweg 1', 'Musterweg 1'],
            'Plz': ['12345', '12345'],
            'Ort': ['Berlin', 'Berlin'],
            'Geburtstag': ['1980-01-01', '1980-01-01'],
            'Jahrgang': [1980, 1980]
        })

        matches = checker.analyze_duplicates(df, confidence_threshold=70.0)

        # Should be 0 because name score < 80 and address assist is off
        self.assertEqual(len(matches), 0)

if __name__ == '__main__':
    unittest.main()
