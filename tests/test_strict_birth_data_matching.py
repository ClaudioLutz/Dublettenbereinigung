"""
Test strict fuzzy/phonetic matching when birth data is missing or poor quality

These tests verify that fuzzy and phonetic matching requires much higher
name similarity when geburtstag or jahrgang data is missing or not matched.
"""
import pytest
import pandas as pd
import numpy as np
from dedupe.scoring import score_pair


def make_test_cols(data_list):
    """Helper to create cols dict from list of test records"""
    df = pd.DataFrame(data_list)
    
    # Fill missing values
    for col in ['vorname', 'name', 'name2', 'strasse', 'hausnummer', 'plz', 'ort']:
        if col not in df.columns:
            df[col] = ''
        else:
            df[col] = df[col].fillna('').astype(str)
    
    if 'dob_ymd' not in df.columns:
        df['dob_ymd'] = -1
    if 'yob' not in df.columns:
        df['yob'] = -1
    
    # Parse house numbers
    df['house_num'] = df['hausnummer'].str.extract(r'^(\d+)')[0].fillna('')
    df['house_sfx'] = df['hausnummer'].str.replace(r'^\d+', '', regex=True).fillna('')
    
    return {
        'first': df['vorname'].str.lower().str.strip(),
        'last': df['name'].str.lower().str.strip(),
        'name2': df['name2'].str.lower().str.strip(),
        'street': df['strasse'].str.lower().str.strip(),
        'house': df['hausnummer'].str.lower().str.strip(),
        'house_num': df['house_num'].str.lower().str.strip(),
        'house_sfx': df['house_sfx'].str.lower().str.strip(),
        'plz': df['plz'].astype(str),
        'ort': df['ort'].str.lower().str.strip(),
        'dob_ymd': df['dob_ymd'],
        'yob': df['yob']
    }


def test_fuzzy_match_rejected_when_both_birth_missing():
    """
    Evalotta vs Evlotta Samuelsson (58% similarity)
    Both geburtstag and jahrgang missing -> REJECT
    """
    data = [
        {
            'vorname': 'Evalotta',
            'name': 'Samuelsson',
            'name2': '',
            'strasse': 'Bahnhofstrasse',
            'hausnummer': '12',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1
        },
        {
            'vorname': 'Evlotta',
            'name': 'Samuelsson',
            'name2': '',
            'strasse': 'Bahnhofstrasse',
            'hausnummer': '12',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    # Should be rejected - ~58% name similarity with no birth data
    assert result is None, "Should reject fuzzy match with ~58% similarity when both birth fields missing"


def test_fuzzy_match_rejected_when_different_surnames_one_jahrgang():
    """
    Rolf Thür vs Rolf Haltner (72.5% similarity)
    Only one has jahrgang, different surnames -> REJECT
    """
    data = [
        {
            'vorname': 'Rolf',
            'name': 'Thür',
            'name2': '',
            'strasse': 'Bahnhofstrasse',
            'hausnummer': '58',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1  # Missing
        },
        {
            'vorname': 'Rolf',
            'name': 'Haltner',
            'name2': '',
            'strasse': 'Bahnhofstrasse',
            'hausnummer': '58',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': 1951  # Has jahrgang
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    # Should be rejected - ~72.5% name similarity with one birth field missing
    # Requires 90%+ when one DOB missing
    assert result is None, "Should reject fuzzy match with different surnames when one jahrgang missing"


def test_phonetic_rejected_when_both_birth_missing():
    """
    Catrin vs Katherina Staub (phonetic match)
    Both missing birth data -> should require 92%+ similarity
    Name similarity is ~70% -> REJECT phonetic
    """
    data = [
        {
            'vorname': 'Catrin',
            'name': 'Staub',
            'name2': '',
            'strasse': 'Stadelhoferstrasse',
            'hausnummer': '10',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1
        },
        {
            'vorname': 'Katherina',
            'name': 'Staub',
            'name2': '',
            'strasse': 'Stadelhoferstrasse',
            'hausnummer': '10',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    # Should be rejected - phonetic match but <92% name similarity with no birth data
    assert result is None, "Should reject phonetic match when both birth fields missing and <92% similarity"


def test_fuzzy_match_accepted_with_exact_dob():
    """
    Similar names with exact DOB match -> should be accepted
    """
    data = [
        {
            'vorname': 'Daniel',
            'name': 'Hager',
            'name2': '',
            'strasse': 'Geigergasse',
            'hausnummer': '5',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': 19650301,
            'yob': 1965
        },
        {
            'vorname': 'Daniel',
            'name': 'Egger',
            'name2': '',
            'strasse': 'Geigergasse',
            'hausnummer': '5',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': 19650301,  # Exact DOB match
            'yob': 1965
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    # Should be accepted - have exact DOB match
    assert result is not None, "Should accept match with exact DOB"
    assert result.reason == 'fuzzy_normal'


def test_phonetic_accepted_with_exact_dob():
    """
    Hans-Peter vs Hans Rudolf Leuzinger (phonetic match)
    Has exact DOB match -> should be accepted
    """
    data = [
        {
            'vorname': 'Hans-Peter',
            'name': 'Leuzinger',
            'name2': '',
            'strasse': 'Zinnengasse',
            'hausnummer': '9',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': 19390110,
            'yob': 1939
        },
        {
            'vorname': 'Hans Rudolf',
            'name': 'Leuzinger',
            'name2': '',
            'strasse': 'Zinnengasse',
            'hausnummer': '9',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': 19390110,  # Exact DOB match
            'yob': 1939
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    # With exact DOB, phonetic should work even with moderate name similarity
    assert result is not None, "Should accept phonetic match with exact DOB"


def test_jahrgang_only_match_requires_88_percent():
    """
    When only jahrgang matches (no exact DOB), require 88%+ similarity
    """
    data = [
        {
            'vorname': 'Büshra',
            'name': 'Ayaz',
            'name2': '',
            'strasse': 'Wettingerwies',
            'hausnummer': '2',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,  # No exact DOB
            'yob': 1982
        },
        {
            'vorname': 'Büsra',
            'name': 'Ayaz',
            'name2': '',
            'strasse': 'Wettingerwies',
            'hausnummer': '2',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,  # No exact DOB
            'yob': 1982  # Same jahrgang
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    # Should be accepted - minor spelling difference with jahrgang match
    # Name similarity should be >88%
    assert result is not None, "Should accept high-similarity match with jahrgang"


def test_address_assisted_blocked_without_exact_dob():
    """
    Address-assisted matching should be blocked when DOB data quality is poor
    """
    data = [
        {
            'vorname': 'Angela Katharina',
            'name': 'Weber',
            'name2': '',
            'strasse': 'Untere Zäune',
            'hausnummer': '1',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1  # No birth data
        },
        {
            'vorname': 'Angela',
            'name': 'Werber',  # Different surname
            'name2': '',
            'strasse': 'Untere Zäune',
            'hausnummer': '1',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1  # No birth data
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80, enable_address_aware=True)
    
    # Should be rejected - address-assisted requires exact DOB or both missing
    # In this case both missing, but name similarity too low (requires 90%+)
    assert result is None, "Should reject address-assisted match without sufficient birth data"


def test_very_high_similarity_accepted_without_birth_data():
    """
    When name similarity is very high (95%+), can match even without birth data
    """
    data = [
        {
            'vorname': 'Andreas',
            'name': 'Schmidt',
            'name2': '',
            'strasse': 'Bahnhofstrasse',
            'hausnummer': '10',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1
        },
        {
            'vorname': 'Andreas',
            'name': 'Schmidt',  # Exact match
            'name2': '',
            'strasse': 'Bahnhofstrasse',
            'hausnummer': '10',
            'plz': '800100',
            'ort': 'Zürich',
            'dob_ymd': -1,
            'yob': -1
        }
    ]
    
    cols = make_test_cols(data)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    # Should be accepted - exact name match (100% similarity)
    assert result is not None, "Should accept exact match even without birth data"
    assert result.reason == 'exact_normal'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
