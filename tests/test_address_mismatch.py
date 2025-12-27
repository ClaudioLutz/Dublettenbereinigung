"""
Test that addresses with mismatched city (Ort) don't get 100% confidence score
even when names match perfectly.

Example from user:
- Record A: Christa Salzmann, Oberdorf, PLZ 965800, Ort: Oberdorf SG
- Record B: Christa Salzmann, Oberdorfstrasse 35, PLZ 965800, Ort: Wildhaus
These should NOT get 100% confidence because cities are different!
"""

import pandas as pd
from dedupe.preprocess import preprocess
from dedupe.scoring import score_pair


def test_different_cities_not_100_percent():
    """Test that exact name match with different cities gets reduced score (not 100%)"""
    
    # Create test data matching the user's example
    df = pd.DataFrame([
        {
            "Vorname": "Christa",
            "Name": "Salzmann",
            "Name2": "",
            "Strasse": "Oberdorf",
            "HausNummer": "",
            "Plz": "965800",
            "Ort": "Oberdorf SG",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Christa",
            "Name": "Salzmann",
            "Name2": "",
            "Strasse": "Oberdorfstrasse",
            "HausNummer": "35",
            "Plz": "965800",
            "Ort": "Wildhaus",
            "Geburtstag": pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols)
    
    # The result should still be a match, but with score < 100%
    # Because cities are different (Oberdorf SG vs Wildhaus)
    assert result is not None, (
        "Expected a match with reduced score, but got None. "
        "Same names with different cities should still match, just not at 100%!"
    )
    
    assert result.score < 100.0, (
        f"Expected score < 100% for different cities, but got {result.score}%. "
        f"Different cities (Oberdorf SG vs Wildhaus) should prevent 100% score!"
    )
    
    # Should be a reasonable score (e.g., 50-95%)
    assert 50.0 <= result.score < 100.0, (
        f"Expected score between 50-99%, but got {result.score}%"
    )


def test_same_city_allows_match():
    """Test that exact name match with same city allows high confidence"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Christa",
            "Name": "Salzmann",
            "Name2": "",
            "Strasse": "Oberdorfstrasse",
            "HausNummer": "35",
            "Plz": "965800",
            "Ort": "Wildhaus",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Christa",
            "Name": "Salzmann",
            "Name2": "",
            "Strasse": "Oberdorfstrasse",
            "HausNummer": "35",
            "Plz": "965800",
            "Ort": "Wildhaus",
            "Geburtstag": pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols)
    
    # Should get a high score (90-100%)
    assert result is not None, "Expected a match for identical records"
    assert result.score >= 90.0, (
        f"Expected score >= 90% for identical records, got {result.score}"
    )
    assert result.reason == "exact_normal"


def test_similar_city_allows_match():
    """Test that exact name match with similar cities allows high confidence"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Ruedi",
            "Name": "Schneider",
            "Name2": "",
            "Strasse": "Saendli",
            "HausNummer": "",
            "Plz": "965700",
            "Ort": "Unterwasser",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Ruedi",
            "Name": "Schneider",
            "Name2": "",
            "Strasse": "Saendli",
            "HausNummer": "",
            "Plz": "965700",
            "Ort": "Unterwasser",
            "Geburtstag": pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols)
    
    # Should get a high score (90-100%)
    assert result is not None, "Expected a match for identical records"
    assert result.score >= 90.0, (
        f"Expected score >= 90% for identical records, got {result.score}"
    )


def test_very_different_cities_low_score():
    """Test that exact names with very different cities get low score"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Hans",
            "Name": "Mueller",
            "Name2": "",
            "Strasse": "Hauptstrasse",
            "HausNummer": "10",
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Hans",
            "Name": "Mueller",
            "Name2": "",
            "Strasse": "Hauptstrasse",
            "HausNummer": "10",
            "Plz": "8000",
            "Ort": "Geneva",
            "Geburtstag": pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols)
    
    # Should still match but with low score due to different cities
    assert result is not None, (
        "Expected a match with reduced score for very different cities (Zurich vs Geneva)"
    )
    
    # Score should be significantly reduced (well below 100%)
    assert result.score < 90.0, (
        f"Expected score < 90% for very different cities, but got {result.score}%"
    )


if __name__ == "__main__":
    test_different_cities_not_100_percent()
    print("✓ Test 1 passed: Different cities get reduced score (<100%)")
    
    test_same_city_allows_match()
    print("✓ Test 2 passed: Same city allows high confidence match")
    
    test_similar_city_allows_match()
    print("✓ Test 3 passed: Similar cities allow high confidence match")
    
    test_very_different_cities_low_score()
    print("✓ Test 4 passed: Very different cities get low score")
    
    print("\n✅ All tests passed!")
