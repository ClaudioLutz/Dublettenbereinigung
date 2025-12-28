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


class TestFullIntegration:
    """Test full integration of swisstopo normalization in preprocess()."""

    @pytest.fixture
    def temp_duckdb(self, tmp_path):
        """Create a temporary DuckDB with swisstopo schema."""
        import duckdb
        db_path = tmp_path / "swisstopo_test.duckdb"
        con = duckdb.connect(str(db_path))

        # Create schema matching what build_swisstopo_index.py creates
        con.execute("""
            CREATE TABLE addresses (
                street_label VARCHAR,
                adr_number VARCHAR,
                plz4 VARCHAR,
                ort VARCHAR,
                adr_egaid VARCHAR,
                bdg_egid VARCHAR,
                adr_official VARCHAR,
                adr_status VARCHAR,
                street_key VARCHAR,
                street_sig VARCHAR,
                house_num VARCHAR
            )
        """)

        # Insert a sample record: "Hofstattstrasse 12, 6377 Seelisberg"
        # Normalized: street_key="hofstatt", street_sig="hofs", house_num="12"
        con.execute("""
            INSERT INTO addresses VALUES (
                'Hofstattstrasse', '12', '6377', 'Seelisberg',
                '1001', '2001', 'true', 'existing',
                'hofstatt', 'hofs', '12'
            )
        """)

        # Insert another record for typo testing: "Bahnhofstrasse 1, 8001 Zurich"
        con.execute("""
            INSERT INTO addresses VALUES (
                'Bahnhofstrasse', '1', '8001', 'Zürich',
                '1002', '2002', 'true', 'existing',
                'bahnhof', 'bahn', '1'
            )
        """)

        con.close()
        return db_path

    def test_preprocess_with_swisstopo(self, temp_duckdb):
        """Test that preprocess uses swisstopo for normalization."""
        from dedupe.preprocess import preprocess
        from dedupe.swisstopo import SwisstopoAddressNormalizer

        normalizer = SwisstopoAddressNormalizer(temp_duckdb)

        # Input: slight variation of the address in DB
        # "Hofstattstrasse" vs "Hofstattstrasse" (match)
        # PLZ "637700" (should become "6377")
        df = pd.DataFrame({
            "Vorname": ["Hans"],
            "Name": ["Müller"],
            "Strasse": ["Hofstattstrasse"],
            "HausNummer": ["12"],
            "Plz": ["637700"],  # PLZ6
            "Ort": ["Seelisberg"]
        })

        out = preprocess(df, address_normalizer=normalizer)

        # Check swisstopo output fields
        assert out["swis_match_type"][0] == "strict"
        assert out["swis_adr_egaid_ref"][0] == "1001"
        assert out["swis_plz4_ref"][0] == "6377"

        # Check blocking keys use PLZ4 and normalized values
        # The db record has 'hofstatt' as street key.
        # Our input 'Hofstattstrasse' normalizes to 'hofstatt' via normalize_street_key too.

        # Let's try a case where it changes.
        # DB: "Bahnhofstrasse", Input: "Bahnhofstr."
        df2 = pd.DataFrame({
            "Vorname": ["Fritz"],
            "Name": ["Meier"],
            "Strasse": ["Bahnhofstr."],
            "HausNummer": ["1"],
            "Plz": ["8001"],
            "Ort": ["Zurich"]
        })

        out2 = preprocess(df2, address_normalizer=normalizer)

        assert out2["swis_match_type"][0] == "sig"
        # Input "Bahnhofstr." -> normalized basic "bahnhofstr" -> key "bahnhofstr" (strict mismatch)
        # DB "Bahnhofstrasse" -> key "bahnhof"
        # Match!

        # Does it overwrite the street?
        # preprocess logic: street = street.where(~mask, ref_street)
        # ref_street comes from ref['street_label_ref'] which is "Bahnhofstrasse"
        # So "Bahnhofstr." should become "bahnhofstrasse" (normalized)

        assert "bahnhofstrasse" in out2["street"][0]
        assert out2["swis_changed"][0] == True

    def test_plz6_handling_in_keys(self, temp_duckdb):
        """Test that PLZ6 is handled correctly in blocking keys."""
        from dedupe.preprocess import preprocess

        # Case where no normalizer is used, but PLZ6 is present
        df = pd.DataFrame({
            "Vorname": ["Hans"],
            "Name": ["Müller"],
            "Strasse": ["Hauptstr"],
            "HausNummer": ["10"],
            "Plz": ["900000"],
            "Ort": ["St. Gallen"]
        })

        out = preprocess(df, address_normalizer=None)

        # Check that blocking keys use 4 digits
        # addr_key_building = plz4 + "|" + street_key + "|" + house_num
        key = out["addr_key_building"][0]
        assert key.startswith("9000|")
        assert "900000" not in key

        # Check plz4_used is stored
        assert out["plz4_used"][0] == "9000"

    def test_preprocess_with_custom_index(self, temp_duckdb):
        """Test preprocess with a custom index DataFrame."""
        from dedupe.preprocess import preprocess
        from dedupe.swisstopo import SwisstopoAddressNormalizer

        normalizer = SwisstopoAddressNormalizer(temp_duckdb)

        df = pd.DataFrame({
            "Vorname": ["Hans"],
            "Name": ["Müller"],
            "Strasse": ["Hofstattstrasse"],
            "HausNummer": ["12"],
            "Plz": ["637700"],
            "Ort": ["Seelisberg"]
        }, index=[100])

        out = preprocess(df, address_normalizer=normalizer)

        # Check alignment
        assert out["swis_match_type"].index[0] == 100
        assert out["swis_match_type"].loc[100] == "strict"
        assert out["plz4_used"].loc[100] == "6377"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
