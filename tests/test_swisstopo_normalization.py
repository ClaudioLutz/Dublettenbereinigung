"""
Test swisstopo address normalization functionality.
"""

import pytest
import pandas as pd
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.preprocess import normalize_street_key, street_signature, _split_street_suffix, extract_plz4


class TestStreetSuffixSplitting:
    """Test concatenated street name splitting."""
    
    def test_split_hofstattstrasse(self):
        """Test splitting 'hofstattstrasse' into 'hofstatt' + 'strasse'."""
        result = _split_street_suffix("hofstattstrasse")
        assert result == ["hofstatt", "strasse"]
    
    def test_split_haldenweg(self):
        """Test splitting 'haldenweg' into 'halden' + 'weg'."""
        result = _split_street_suffix("haldenweg")
        assert result == ["halden", "weg"]
    
    def test_split_bahnhofplatz(self):
        """Test splitting 'bahnhofplatz' into 'bahnhof' + 'platz'."""
        result = _split_street_suffix("bahnhofplatz")
        assert result == ["bahnhof", "platz"]
    
    def test_no_split_short_token(self):
        """Test that short tokens are not split."""
        result = _split_street_suffix("abc")
        assert result == ["abc"]
    
    def test_no_split_no_suffix(self):
        """Test that tokens with 'hof' suffix are split correctly."""
        # Note: "hauptbahnhof" ends with "hof" which is a known suffix, so it WILL be split
        result = _split_street_suffix("hauptbahnhof")
        assert result == ["hauptbahn", "hof"]
    
    def test_no_split_insufficient_root(self):
        """Test that we don't split if root would be too short."""
        result = _split_street_suffix("strasse")
        assert result == ["strasse"]  # Would leave empty root


class TestStreetNormalizationWithSuffixes:
    """Test that street normalization handles concatenated names."""
    
    def test_normalize_hofstattstrasse(self):
        """Test that 'hofstattstrasse' normalizes to 'hofstatt'."""
        series = pd.Series(["hofstattstrasse"])
        result = normalize_street_key(series)
        assert result.iloc[0] == "hofstatt"
    
    def test_normalize_maintains_multiple_tokens(self):
        """Test that multi-token streets are preserved."""
        series = pd.Series(["rue de la prairie"])
        result = normalize_street_key(series)
        # Should remove 'rue' and 'de' and 'la' but keep 'prairie'
        assert "prairie" in result.iloc[0]
    
    def test_street_signature_hofstattstrasse(self):
        """Test that street signature handles concatenated names."""
        series = pd.Series(["hofstattstrasse"])
        result = street_signature(series)
        # Should split to 'hofstatt' + 'strasse', remove 'strasse', keep first 4 of 'hofstatt'
        assert result.iloc[0] == "hofs"


class TestSwisstopoIntegration:
    """Test swisstopo normalization with example data."""
    
    @pytest.fixture
    def example_csv_path(self):
        """Path to example swisstopo CSV."""
        return Path("amtliches-gebaeudeadressverzeichnis_ch_2056.csv/amtliches-gebaeudeadressverzeichnis_ch_2056_example.csv")
    
    def test_example_csv_exists(self, example_csv_path):
        """Verify example CSV exists."""
        assert example_csv_path.exists(), f"Example CSV not found at {example_csv_path}"
    
    def test_example_csv_structure(self, example_csv_path):
        """Verify example CSV has expected columns."""
        df = pd.read_csv(example_csv_path, sep=';', nrows=5)
        required_columns = ['ADR_EGAID', 'STN_LABEL', 'ADR_NUMBER', 'ZIP_LABEL', 'ADR_STATUS', 'ADR_OFFICIAL']
        for col in required_columns:
            assert col in df.columns, f"Missing required column: {col}"
    
    def test_normalize_example_addresses(self, example_csv_path):
        """Test normalization of addresses from example CSV."""
        from dedupe.preprocess import _norm_series, parse_house_number
        
        df = pd.read_csv(example_csv_path, sep=';', nrows=5)
        
        # Normalize street names
        street_series = _norm_series(df['STN_LABEL'])
        street_keys = normalize_street_key(street_series)
        
        # Check that we get reasonable results
        assert len(street_keys) == len(df)
        assert all(isinstance(s, str) for s in street_keys)
        
        # Check specific case: Hofstattstrasse should become 'hofstatt'
        hofstatt_mask = df['STN_LABEL'] == 'Hofstattstrasse'
        if hofstatt_mask.any():
            assert street_keys[hofstatt_mask].iloc[0] == "hofstatt"


class TestPlz4Extraction:
    """Test PLZ4 extraction from 6-digit postcodes."""
    
    def test_extract_plz4_from_6_digit(self):
        """Test extracting 4-digit PLZ from 6-digit postcode."""
        series = pd.Series(["965800", "900000", "800000"])
        result = extract_plz4(series)
        assert result.iloc[0] == "9658"
        assert result.iloc[1] == "9000"
        assert result.iloc[2] == "8000"
    
    def test_extract_plz4_from_4_digit(self):
        """Test that 4-digit postcodes pass through unchanged."""
        series = pd.Series(["8000", "6377", "7000"])
        result = extract_plz4(series)
        assert result.iloc[0] == "8000"
        assert result.iloc[1] == "6377"
        assert result.iloc[2] == "7000"
    
    def test_extract_plz4_empty_string(self):
        """Test handling of empty strings."""
        series = pd.Series(["", ""])
        result = extract_plz4(series)
        assert result.iloc[0] == ""
        assert result.iloc[1] == ""
    
    def test_extract_plz4_with_non_digits(self):
        """Test handling of postcodes with non-digit characters."""
        series = pd.Series(["8000-00", "CH-8000"])
        result = extract_plz4(series)
        assert result.iloc[0] == "8000"
        assert result.iloc[1] == "8000"


class TestAddressNormalizerBasics:
    """Test SwisstopoAddressNormalizer basic functionality."""
    
    def test_normalizer_requires_db_file(self):
        """Test that normalizer requires an existing database file."""
        from dedupe.swisstopo import SwisstopoAddressNormalizer
        
        with pytest.raises(FileNotFoundError):
            SwisstopoAddressNormalizer("nonexistent.duckdb")
    
    def test_preprocess_accepts_normalizer_parameter(self):
        """Test that preprocess() accepts address_normalizer parameter."""
        from dedupe.preprocess import preprocess
        import inspect
        
        sig = inspect.signature(preprocess)
        assert 'address_normalizer' in sig.parameters


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
