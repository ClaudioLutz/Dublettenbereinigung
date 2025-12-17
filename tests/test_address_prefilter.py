
import unittest
import pandas as pd
import numpy as np
from duplicate_checker_optimized import (
    normalize_street,
    compute_normalized_address_ratio_fast,
    determine_address_assisted_match_type,
    calculate_address_assisted_confidence,
    process_block_worker,
    VectorizedAddressNormalizer
)
import sys

# Mock rapidfuzz if not installed (though it should be)
try:
    from rapidfuzz import fuzz
except ImportError:
    import warnings
    warnings.warn("rapidfuzz not found, tests might fail")

class TestAddressPrefilter(unittest.TestCase):

    def test_normalize_street(self):
        """Test street normalization logic"""
        # Basic normalization
        self.assertEqual(normalize_street("Bahnhofstrasse"), "bahnhofstrasse")
        self.assertEqual(normalize_street("  Bahnhofstrasse  "), "bahnhofstrasse")

        # Abbreviations
        self.assertEqual(normalize_street("Bahnhofstr."), "bahnhofstrasse")
        self.assertEqual(normalize_street("Hauptstr"), "hauptstrasse")
        self.assertEqual(normalize_street("Bergweg"), "bergweg")

        # Special characters
        self.assertEqual(normalize_street("Hauptstraße"), "hauptstrasse") # ß -> ss
        self.assertEqual(normalize_street("Müllerstraße"), "muellerstrasse") # ü -> ue, ß -> ss
        self.assertEqual(normalize_street("Ölweg"), "oelweg") # Ö -> oe

        # Punctuation removal
        self.assertEqual(normalize_street("Dr.-Meyer-Str."), "dr meyer strasse")

        # Empty/None
        self.assertEqual(normalize_street(None), "")
        self.assertEqual(normalize_street(""), "")
        self.assertEqual(normalize_street("   "), "")

    def test_compute_normalized_address_ratio_fast(self):
        """Test normalized address ratio computation"""

        # Case 1: Perfect match
        rec_a = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8001'}
        rec_b = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8001'}
        ratio = compute_normalized_address_ratio_fast(rec_a, rec_b)
        self.assertEqual(ratio, 1.0)

        # Case 2: Different PLZ (0.6 * 0 + 0.4 * 1.0 = 0.4)
        rec_a = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8001'}
        rec_b = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8002'}
        ratio = compute_normalized_address_ratio_fast(rec_a, rec_b)
        self.assertAlmostEqual(ratio, 0.4)

        # Case 3: Different Street (0.6 * 1.0 + 0.4 * 0.0 = 0.6) - assuming completely different street
        rec_a = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8001'}
        rec_b = {'street_normalized': 'hauptstrasse', 'plz_normalized': '8001'}
        ratio = compute_normalized_address_ratio_fast(rec_a, rec_b)
        # Ratio between bahnhofstrasse and hauptstrasse is likely not 0, but low.
        # Let's check with empty street to be sure of the math
        rec_b['street_normalized'] = ''
        # If one is empty, street ratio is 0.0
        ratio = compute_normalized_address_ratio_fast(rec_a, rec_b)
        self.assertEqual(ratio, 0.6) # Only PLZ matches

        # Case 4: PLZ match, Street similar (Bahnhofstrasse vs Bahnhofstr -> normalized to same)
        # Note: compute_normalized_address_ratio_fast expects already normalized inputs
        rec_a = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8001'}
        rec_b = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8001'}
        ratio = compute_normalized_address_ratio_fast(rec_a, rec_b)
        self.assertEqual(ratio, 1.0)

        # Case 5: PLZ match, Street typo
        rec_a = {'street_normalized': 'bahnhofstrasse', 'plz_normalized': '8001'}
        rec_b = {'street_normalized': 'banhofstrasse', 'plz_normalized': '8001'}
        ratio = compute_normalized_address_ratio_fast(rec_a, rec_b)
        # fuzz.ratio('bahnhofstrasse', 'banhofstrasse') is around 96
        # 0.6 * 1 + 0.4 * 0.96 = 0.984
        self.assertTrue(ratio > 0.9)

    def test_determine_address_assisted_match_type(self):
        self.assertEqual(determine_address_assisted_match_type(False, False), 'address_assisted_normal')
        self.assertEqual(determine_address_assisted_match_type(True, False), 'address_assisted_swapped')
        # Phonetic flag shouldn't change the type logic based on the spec, but check signature
        self.assertEqual(determine_address_assisted_match_type(False, True), 'address_assisted_normal')

    def test_calculate_address_assisted_confidence(self):
        # Normal
        # 70 + 1.0 * 10 = 80
        self.assertEqual(calculate_address_assisted_confidence('address_assisted_normal', 1.0), 80.0)
        # 70 + 0.75 * 10 = 77.5
        self.assertEqual(calculate_address_assisted_confidence('address_assisted_normal', 0.75), 77.5)

        # Swapped
        # 68 + 1.0 * 10 = 78
        self.assertEqual(calculate_address_assisted_confidence('address_assisted_swapped', 1.0), 78.0)
        # 68 + 0.75 * 10 = 75.5
        self.assertEqual(calculate_address_assisted_confidence('address_assisted_swapped', 0.75), 75.5)

    def test_integration_strong_address_noisy_name(self):
        """Test the full flow for 'Strong Address, Noisy Name' case"""

        # Prepare data frame with 2 records
        # "Jonathan" vs "Jon" -> 46%
        # "Smith" vs "Smyth" -> 80%
        # Avg: 63% -> Should trigger the borderline logic (0.60 <= score < 0.70)
        data = {
            'Crefo': ['A', 'B'],
            'Vorname': ['Jonathan', 'Jon'],
            'Name': ['Smith', 'Smyth'],
            'Name2': ['', ''],
            'Strasse': ['Bahnhofstrasse', 'Bahnhofstr.'], # Variation requires normalization
            'HausNummer': ['10', '10'],
            'Plz': ['8001', '8001'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': ['1980-05-15', '1980-05-15'],
            'Jahrgang': ['', ''],
            'index': [0, 1]
        }
        df = pd.DataFrame(data)

        # Args: block_key, block_df, confidence_threshold, fuzzy_threshold
        matches = process_block_worker(('test_block', df, 70.0, 0.70))

        # Assert match is found
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual(match['match_type'], 'address_assisted_normal')
        self.assertTrue(match['confidence_score'] >= 70.0)
        self.assertTrue(match['details']['address_ratio'] >= 0.75)

    def test_integration_weak_address_borderline_name(self):
        """Test rejection when address is weak"""
        # Same names (borderline), but different address
        data = {
            'Crefo': ['A', 'B'],
            'Vorname': ['Jonathan', 'Jon'],
            'Name': ['Smith', 'Smyth'],
            'Name2': ['', ''],
            'Strasse': ['Dorfstrasse', 'Hauptstrasse'], # Different
            'HausNummer': ['1', '20'],
            'Plz': ['5000', '6000'], # Different
            'Ort': ['Aarau', 'Luzern'],
            'Geburtstag': ['1990-07-25', '1990-07-25'],
            'Jahrgang': ['', ''],
            'index': [0, 1]
        }
        df = pd.DataFrame(data)

        matches = process_block_worker(('test_block', df, 70.0, 0.70))

        # Should be empty
        self.assertEqual(len(matches), 0)

if __name__ == '__main__':
    unittest.main()
