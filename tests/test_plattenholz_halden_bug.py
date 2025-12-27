"""
Test for the specific bug: Hans Forrer with completely different streets should NOT match
- Record A: Hans Forrer, Plattenholz, 965800 Wildhaus
- Record B: Hans Forrer, Halden 436, 965800 Wildhaus

These are COMPLETELY DIFFERENT STREETS and should be REJECTED!
"""

import pandas as pd
from dedupe.preprocess import preprocess
from dedupe.scoring import score_pair


def test_completely_different_streets_rejected():
    """Test that exact name match with completely different streets is REJECTED"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Hans",
            "Name": "Forrer",
            "Name2": "",
            "Strasse": "Plattenholz",
            "HausNummer": "",
            "Plz": "965800",
            "Ort": "Wildhaus",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Hans",
            "Name": "Forrer",
            "Name2": "",
            "Strasse": "Halden",
            "HausNummer": "436",
            "Plz": "965800",
            "Ort": "Wildhaus",
            "Geburtstag": pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols)
    
    # Should be REJECTED because streets are completely different
    # "Plattenholz" vs "Halden" are NOT similar streets!
    assert result is None, (
        f"❌ BUG STILL EXISTS! Hans Forrer with completely different streets "
        f"(Plattenholz vs Halden) should be REJECTED, but got match with score {result.score if result else 'None'}!"
    )
    
    print("✅ FIXED! Completely different streets now correctly rejected")
    print("   Hans Forrer: Plattenholz vs Halden → REJECTED ✓")


if __name__ == "__main__":
    test_completely_different_streets_rejected()
    print("\n✅ Bug fix verified!")
