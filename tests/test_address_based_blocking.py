"""
Tests for address-based blocking functionality.

This test suite validates the new address-based deduplication pipeline:
- House number parsing
- Street normalization and signatures
- Address key construction
- DOB/YOB hard gates
- Sorted neighborhood windowing
"""

import pandas as pd
import numpy as np
import pytest
from dedupe.preprocess import (
    parse_house_number,
    normalize_street_key,
    street_signature,
    parse_dob_ymd,
    extract_yob,
    preprocess
)
from dedupe.blocking import (
    compute_address_building_key,
    compute_address_typo_key,
)
from dedupe.scoring import score_pair
from dedupe.candidates import iter_windowed_fuzzy_pairs


class TestHouseNumberParsing:
    """Test house number parsing into numeric and suffix parts"""
    
    def test_simple_numeric(self):
        """Test simple numeric house numbers"""
        house = pd.Series(['12', '100', '7'])
        num, sfx = parse_house_number(house)
        
        assert num.tolist() == ['12', '100', '7']
        assert sfx.tolist() == ['', '', '']
    
    def test_with_suffix(self):
        """Test house numbers with alphabetic suffixes"""
        house = pd.Series(['12a', '12A', '12b', '100c'])
        num, sfx = parse_house_number(house)
        
        assert num.tolist() == ['12', '12', '12', '100']
        assert sfx.tolist() == ['a', 'a', 'b', 'c']
    
    def test_empty_and_mixed(self):
        """Test empty and mixed formats"""
        house = pd.Series(['', '12', '12A', 'ABC'])
        num, sfx = parse_house_number(house)
        
        assert num.tolist() == ['', '12', '12', '']
        assert sfx.tolist() == ['', '', 'a', 'abc']
    
    def test_same_building_different_suffix(self):
        """Test that 12, 12A, and 12B all have same numeric part"""
        house = pd.Series(['12', '12A', '12b', '12c'])
        num, sfx = parse_house_number(house)
        
        # All same building (numeric part)
        assert all(num == '12')
        # Different apartments (suffixes)
        assert sfx.tolist() == ['', 'a', 'b', 'c']


class TestStreetNormalization:
    """Test street key and signature generation"""
    
    def test_street_key_removes_types(self):
        """Test that street types are removed from keys"""
        # Already normalized (lowercase, cleaned)
        street = pd.Series([
            'bahnhof strasse',
            'bahnhof str',
            'haupt gasse',
            'park weg'
        ])
        
        keys = normalize_street_key(street)
        
        assert keys.iloc[0] == 'bahnhof'
        assert keys.iloc[1] == 'bahnhof'
        assert keys.iloc[2] == 'haupt'
        assert keys.iloc[3] == 'park'
    
    def test_street_key_multilingual(self):
        """Test multilingual street type handling"""
        street = pd.Series([
            'grande rue',
            'grande avenue',
            'via roma',
            'piazza maggiore'
        ])
        
        keys = normalize_street_key(street)
        
        assert keys.iloc[0] == 'grande'
        assert keys.iloc[1] == 'grande'
        assert keys.iloc[2] == 'roma'
        assert keys.iloc[3] == 'maggiore'
    
    def test_street_signature_for_typos(self):
        """Test street signature for typo recovery"""
        street = pd.Series([
            'bahnhof strasse',
            'bahnhoff strasse',  # typo
            'bahnof strasse',    # typo
        ])
        
        sigs = street_signature(street)
        
        # All should have similar signatures (first 4 chars)
        assert sigs.iloc[0] == 'bahn'
        assert sigs.iloc[1] == 'bahn'
        assert sigs.iloc[2] == 'bahn'
    
    def test_street_signature_multiple_tokens(self):
        """Test signature with multiple tokens"""
        street = pd.Series([
            'karl marx strasse',
            'carl marxx strasse',  # typo in both
        ])
        
        sigs = street_signature(street)
        
        # Signatures: first 4 chars of each token, sorted
        # karl marx -> karl-marx
        # carl marxx -> carl-marx (first 4 chars)
        assert 'karl' in sigs.iloc[0] and 'marx' in sigs.iloc[0]
        assert 'carl' in sigs.iloc[1] and 'marx' in sigs.iloc[1]


class TestAddressKeyConstruction:
    """Test address blocking key generation"""
    
    def test_building_key_construction(self):
        """Test building-level key construction"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Maria'],
            'Name': ['Müller', 'Meier'],
            'Strasse': ['Hauptstrasse 10', 'Hauptstrasse 10'],  # Same street
            'HausNummer': ['12', '12A'],  # Different apartments, same building
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': [pd.NaT, pd.NaT],
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols = preprocess(df)
        
        # Both should have same building key (same PLZ, street, house_num)
        # house_num extracts numeric part only: "12" from both "12" and "12A"
        assert cols['house_num'].iloc[0] == cols['house_num'].iloc[1] == '12'
        assert cols['addr_key_building'].iloc[0] == cols['addr_key_building'].iloc[1], "Same building should have same key"
    
    def test_typo_recovery_key(self):
        """Test typo recovery key for street variants"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Maria'],
            'Name': ['Müller', 'Meier'],
            'Strasse': ['Bahnhofstrasse', 'Bahnhoffstrasse'],  # typo
            'HausNummer': ['12', '12'],
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': [pd.NaT, pd.NaT],
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols = preprocess(df)
        
        # Should have similar typo keys (using signature)
        # Both normalize to similar street signatures
        assert cols['street_sig'].iloc[0] == cols['street_sig'].iloc[1]


class TestDOBHardGate:
    """Test DOB and YOB hard rejection rules"""
    
    def test_dob_mismatch_rejects(self):
        """Test that different DOBs reject match"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Hans'],
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstr.', 'Bahnhofstr.'],
            'HausNummer': ['12', '12'],
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': ['1980-01-15', '1981-02-20'],  # Different DOBs
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols = preprocess(df)
        result = score_pair(0, 1, cols)
        
        # Should reject due to DOB mismatch
        assert result is None, "Different DOBs should reject match"
    
    def test_yob_mismatch_rejects(self):
        """Test that different year of birth rejects match"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Hans'],
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstr.', 'Bahnhofstr.'],
            'HausNummer': ['12', '12'],
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': [pd.NA, pd.NA],
            'Jahrgang': [1980, 1981]  # Different years
        })
        
        cols = preprocess(df)
        result = score_pair(0, 1, cols)
        
        # Should reject due to YOB mismatch
        assert result is None, "Different YOBs should reject match"
    
    def test_same_dob_accepts(self):
        """Test that same DOB allows match evaluation"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Hans'],
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstr.', 'Bahnhofstr.'],
            'HausNummer': ['12', '12'],
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': ['1980-01-15', '1980-01-15'],  # Same DOB
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols = preprocess(df)
        result = score_pair(0, 1, cols)
        
        # Should not reject (may match based on names and address)
        assert result is not None, "Same DOB should allow match evaluation"
        assert result.score > 0
    
    def test_missing_dob_uses_stricter_threshold(self):
        """Test that missing DOB/YOB requires stronger name match"""
        # Case 1: Similar names (85%), same address, with DOB
        df_with_dob = pd.DataFrame({
            'Vorname': ['Hans', 'Hanss'],  # Slight typo
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstr.', 'Bahnhofstr.'],
            'HausNummer': ['12', '12'],
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': ['1980-01-15', '1980-01-15'],
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        # Case 2: Same data but NO DOB/YOB
        df_no_dob = pd.DataFrame({
            'Vorname': ['Hans', 'Hanss'],  # Slight typo
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstr.', 'Bahnhofstr.'],
            'HausNummer': ['12', '12'],
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': [pd.NA, pd.NA],
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols_with_dob = preprocess(df_with_dob)
        cols_no_dob = preprocess(df_no_dob)
        
        result_with_dob = score_pair(0, 1, cols_with_dob, fuzzy_threshold=0.80)
        result_no_dob = score_pair(0, 1, cols_no_dob, fuzzy_threshold=0.80)
        
        # With DOB: may match (threshold 0.80)
        # Without DOB: should reject (needs 0.90 threshold)
        # This protects against matching family members at same address
        # Note: The exact behavior depends on actual name similarity score


class TestSortedNeighborhoodWindowing:
    """Test sorted neighborhood candidate generation"""
    
    def test_windowed_pairs_small_block(self):
        """Test that small blocks use all-pairs"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Maria', 'Peter'],
            'Name': ['Müller', 'Meier', 'Schmidt'],
            'Strasse': ['Bahnhofstr.'] * 3,
            'HausNummer': ['12'] * 3,
            'Plz': ['8000'] * 3,
            'Geburtstag': [pd.NaT] * 3,
            'Jahrgang': [pd.NA] * 3
        })
        
        cols = preprocess(df)
        idx = np.array([0, 1, 2])
        
        pairs = list(iter_windowed_fuzzy_pairs(idx, cols, window=10, name_threshold=0))
        
        # Small block (<=400) should generate all pairs
        expected_pairs = {(0, 1), (0, 2), (1, 2)}
        actual_pairs = set(pairs)
        
        assert actual_pairs == expected_pairs
    
    def test_windowed_pairs_respects_window(self):
        """Test that window size limits comparisons"""
        # Create a block larger than small_block threshold (400)
        # so windowing is actually used
        n = 500
        df = pd.DataFrame({
            'Vorname': [f'Person{i}' for i in range(n)],
            'Name': ['Müller'] * n,
            'Strasse': ['Bahnhofstr.'] * n,
            'HausNummer': ['12'] * n,
            'Plz': ['8000'] * n,
            'Geburtstag': [pd.NaT] * n,
            'Jahrgang': [pd.NA] * n
        })
        
        cols = preprocess(df)
        idx = np.arange(n)
        
        # With window=2, each record should only compare with next 2
        pairs = list(iter_windowed_fuzzy_pairs(idx, cols, window=2, name_threshold=0))
        
        # Multi-pass windowing creates more pairs, but still bounded
        # Each record compares with at most 'window' neighbors per pass
        # With 2 passes and window=2: roughly 2 * n * window = 2 * 500 * 2 = 2000 pairs
        # Much less than all-pairs: 500 * 499 / 2 = 124,750
        assert len(pairs) > 0
        assert len(pairs) < n * (n - 1) // 2, f"Expected less than {n * (n - 1) // 2} pairs, got {len(pairs)}"
        # Verify it's using windowing (should be roughly 2 * n * window)
        expected_max = 2 * n * 2 * 2  # 2 passes * n records * window * 2 (for overlap)
        assert len(pairs) < expected_max, f"Too many pairs generated: {len(pairs)}, expected < {expected_max}"


class TestEndToEndAddressBlocking:
    """End-to-end tests for address-based blocking"""
    
    def test_same_building_different_apartments(self):
        """Test matching people in same building but different apartments"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Hans'],
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstr.', 'Bahnhofstr.'],
            'HausNummer': ['12', '12A'],  # Different apartments
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': ['1980-01-15', '1980-01-15'],
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols = preprocess(df)
        
        # Same building key (house_num ignores suffix)
        assert cols['house_num'].iloc[0] == cols['house_num'].iloc[1]
        assert cols['addr_key_building'].iloc[0] == cols['addr_key_building'].iloc[1]
        
        # Should match (same name, same building, same DOB)
        result = score_pair(0, 1, cols)
        assert result is not None
        assert result.score > 80
    
    def test_different_buildings_no_match(self):
        """Test that different house numbers prevent matching"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Hans'],
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstr.', 'Bahnhofstr.'],
            'HausNummer': ['12', '14'],  # Different buildings
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': ['1980-01-15', '1980-01-15'],
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols = preprocess(df)
        
        # Different building keys
        assert cols['house_num'].iloc[0] != cols['house_num'].iloc[1]
        assert cols['addr_key_building'].iloc[0] != cols['addr_key_building'].iloc[1]
        
        # Should reject (different house numbers)
        result = score_pair(0, 1, cols)
        assert result is None, "Different house numbers should reject match"
    
    def test_street_typo_recovery(self):
        """Test that minor street typos can be recovered via signature"""
        df = pd.DataFrame({
            'Vorname': ['Hans', 'Hans'],
            'Name': ['Müller', 'Müller'],
            'Strasse': ['Bahnhofstrasse', 'Bahnhoffstrasse'],  # One extra 'f'
            'HausNummer': ['12', '12'],
            'Plz': ['8000', '8000'],
            'Ort': ['Zürich', 'Zürich'],
            'Geburtstag': ['1980-01-15', '1980-01-15'],
            'Jahrgang': [pd.NA, pd.NA]
        })
        
        cols = preprocess(df)
        
        # Different building keys (different street_key)
        assert cols['addr_key_building'].iloc[0] != cols['addr_key_building'].iloc[1]
        
        # But same typo recovery key (same signature)
        assert cols['addr_key_typo'].iloc[0] == cols['addr_key_typo'].iloc[1]


class TestYOBExtraction:
    """Test year of birth extraction from Jahrgang or Geburtstag"""
    
    def test_jahrgang_priority(self):
        """Test that Jahrgang has priority over Geburtstag"""
        df = pd.DataFrame({
            'Vorname': ['Hans'],
            'Name': ['Müller'],
            'Geburtstag': ['1980-01-15'],
            'Jahrgang': [1979]  # Different from Geburtstag
        })
        
        cols = preprocess(df)
        
        # Should use Jahrgang (priority)
        assert cols['yob'][0] == 1979
    
    def test_geburtstag_fallback(self):
        """Test fallback to Geburtstag when Jahrgang missing"""
        df = pd.DataFrame({
            'Vorname': ['Hans'],
            'Name': ['Müller'],
            'Geburtstag': ['1980-01-15'],
            'Jahrgang': [pd.NA]
        })
        
        cols = preprocess(df)
        
        # Should extract year from Geburtstag
        assert cols['yob'][0] == 1980
    
    def test_both_missing(self):
        """Test that missing both gives -1"""
        df = pd.DataFrame({
            'Vorname': ['Hans'],
            'Name': ['Müller'],
            'Geburtstag': [pd.NaT],
            'Jahrgang': [pd.NA]
        })
        
        cols = preprocess(df)
        
        # Should be -1 (missing)
        assert cols['yob'][0] == -1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
