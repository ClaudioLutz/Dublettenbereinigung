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


class TestMultilingualTypePreservation:
    """Test type-preserving normalization for German/French/Italian."""
    
    def test_german_gasse_vs_hof_collision(self):
        """Test that Augustinergasse and Augustinerhof don't collide."""
        from dedupe.preprocess import normalize_street_full, street_signature_full
        
        # These should produce DIFFERENT keys (type-preserving)
        gasse = pd.Series(["augustiner gasse"])
        hof = pd.Series(["augustiner hof"])
        
        gasse_full = normalize_street_full(gasse).iloc[0]
        hof_full = normalize_street_full(hof).iloc[0]
        
        assert gasse_full != hof_full, "Gasse and Hof should not collide"
        assert "gasse" in gasse_full
        assert "hof" in hof_full
        
        # Signatures should also differ
        gasse_sig = street_signature_full(gasse).iloc[0]
        hof_sig = street_signature_full(hof).iloc[0]
        
        assert gasse_sig != hof_sig, "Gasse and Hof signatures should not collide"
    
    def test_german_platz_vs_strasse_collision(self):
        """Test that Zähringer Platz and Zähringer Strasse don't collide."""
        from dedupe.preprocess import normalize_street_full, street_signature_full
        
        platz = pd.Series(["zaehringer platz"])
        strasse = pd.Series(["zaehringer strasse"])
        
        platz_full = normalize_street_full(platz).iloc[0]
        strasse_full = normalize_street_full(strasse).iloc[0]
        
        assert platz_full != strasse_full
        assert "platz" in platz_full
        assert "strasse" in strasse_full
    
    def test_french_rue_vs_route_collision(self):
        """Test that Rue and Route don't collide."""
        from dedupe.preprocess import normalize_street_full, street_signature_full
        
        rue = pd.Series(["rue de la gare"])
        route = pd.Series(["route de la gare"])
        
        rue_full = normalize_street_full(rue).iloc[0]
        route_full = normalize_street_full(route).iloc[0]
        
        assert rue_full != route_full
        assert "rue" in rue_full
        assert "route" in route_full
    
    def test_french_abbreviation_canonicalization(self):
        """Test that French abbreviations are canonicalized correctly."""
        from dedupe.preprocess import normalize_street_full
        
        # "av" should become "avenue"
        av = pd.Series(["av de la gare"])
        avenue = pd.Series(["avenue de la gare"])
        
        av_full = normalize_street_full(av).iloc[0]
        avenue_full = normalize_street_full(avenue).iloc[0]
        
        # Both should normalize to same canonical form
        assert av_full == avenue_full
        assert "avenue" in av_full
    
    def test_italian_via_vs_viale_collision(self):
        """Test that Via and Viale don't collide."""
        from dedupe.preprocess import normalize_street_full, street_signature_full
        
        via = pd.Series(["via roma"])
        viale = pd.Series(["viale roma"])
        
        via_full = normalize_street_full(via).iloc[0]
        viale_full = normalize_street_full(viale).iloc[0]
        
        assert via_full != viale_full
        assert "via" in via_full
        assert "viale" in viale_full


class TestAmbiguityGuard:
    """Test ambiguity guard that prevents overwriting on non-unique matches."""
    
    @pytest.fixture
    def ambiguous_db(self, tmp_path):
        """Create a DB with ambiguous addresses (same PLZ/key/house, different streets)."""
        import duckdb
        db_path = tmp_path / "ambiguous_test.duckdb"
        con = duckdb.connect(str(db_path))
        
        # Create schema with type-preserving keys
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
                street_full VARCHAR,
                street_sig_full VARCHAR,
                house_num VARCHAR
            )
        """)
        
        # Insert TWO addresses that would collide with old logic:
        # "Augustinergasse 8" and "Augustinerhof 8" in same PLZ
        # With old street_key (type-less), both become "augustiner"
        # With new street_full (type-preserving), they stay distinct
        con.execute("""
            INSERT INTO addresses VALUES (
                'Augustinergasse', '8', '8001', 'Zürich',
                '1001', '2001', 'true', 'existing',
                'augustiner', 'augu', 'augustiner gasse', 'augu-gass', '8'
            )
        """)
        
        con.execute("""
            INSERT INTO addresses VALUES (
                'Augustinerhof', '8', '8001', 'Zürich',
                '1002', '2002', 'true', 'existing',
                'augustiner', 'augu', 'augustiner hof', 'augu-hof', '8'
            )
        """)
        
        # Add indexes
        con.execute("CREATE INDEX idx_full ON addresses(plz4, street_full, house_num)")
        con.execute("CREATE INDEX idx_sig_full ON addresses(plz4, street_sig_full, house_num)")
        
        con.close()
        return db_path
    
    def test_augustinergasse_no_collision(self, ambiguous_db):
        """Test that Augustinergasse 8 matches correctly (not Augustinerhof)."""
        from dedupe.preprocess import preprocess
        from dedupe.swisstopo import SwisstopoAddressNormalizer
        
        normalizer = SwisstopoAddressNormalizer(ambiguous_db)
        
        # Input: "Augustinergasse 8"
        df = pd.DataFrame({
            "Vorname": ["Hans"],
            "Name": ["Müller"],
            "Strasse": ["Augustinergasse"],
            "HausNummer": ["8"],
            "Plz": ["8001"],
            "Ort": ["Zürich"]
        })
        
        out = preprocess(df, address_normalizer=normalizer)
        
        # Should match with type-preserving key
        assert out["swis_match_type"][0] == "strict"
        assert out["swis_adr_egaid_ref"][0] == "1001"  # Gasse, not Hof
        assert "gasse" in out["swis_street_label_ref"][0].lower()
        assert "hof" not in out["swis_street_label_ref"][0].lower()
    
    def test_augustinerhof_no_collision(self, ambiguous_db):
        """Test that Augustinerhof 8 matches correctly (not Augustinergasse)."""
        from dedupe.preprocess import preprocess
        from dedupe.swisstopo import SwisstopoAddressNormalizer
        
        normalizer = SwisstopoAddressNormalizer(ambiguous_db)
        
        # Input: "Augustinerhof 8"
        df = pd.DataFrame({
            "Vorname": ["Fritz"],
            "Name": ["Meier"],
            "Strasse": ["Augustinerhof"],
            "HausNummer": ["8"],
            "Plz": ["8001"],
            "Ort": ["Zürich"]
        })
        
        out = preprocess(df, address_normalizer=normalizer)
        
        # Should match with type-preserving key
        assert out["swis_match_type"][0] == "strict"
        assert out["swis_adr_egaid_ref"][0] == "1002"  # Hof, not Gasse
        assert "hof" in out["swis_street_label_ref"][0].lower()
        assert "gasse" not in out["swis_street_label_ref"][0].lower()
    
    def test_candidate_count_in_output(self, ambiguous_db):
        """Test that candidate_count is computed correctly."""
        from dedupe.swisstopo import SwisstopoAddressNormalizer
        
        normalizer = SwisstopoAddressNormalizer(ambiguous_db)
        
        # Build keys for a query
        keys_df = pd.DataFrame({
            'row_id': [0],
            'plz4': ['8001'],
            'street_key': ['augustiner'],  # Legacy - would match both
            'street_sig': ['augu'],  # Legacy - would match both
            'street_full': ['augustiner gasse'],  # Type-preserving - unique
            'street_sig_full': ['augu-gass'],  # Type-preserving - unique
            'house_num': ['8']
        })
        
        result = normalizer.normalize_chunk(keys_df)
        
        # Should have unique match with type-preserving key
        assert len(result) == 1
        assert result['candidate_count'].iloc[0] == 1
        assert result['adr_egaid_ref'].iloc[0] == '1001'  # Gasse


class TestStreetTypeCanonicalization:
    """Test street type canonicalization mappings."""
    
    def test_german_str_to_strasse(self):
        """Test that 'str' canonicalizes to 'strasse'."""
        from dedupe.preprocess import normalize_street_full
        
        # Use separate tokens for canonicalization test
        str_form = pd.Series(["haupt str"])
        strasse_form = pd.Series(["haupt strasse"])
        
        str_full = normalize_street_full(str_form).iloc[0]
        strasse_full = normalize_street_full(strasse_form).iloc[0]
        
        # Both should normalize to same form
        assert str_full == strasse_full
        assert "strasse" in str_full
    
    def test_french_av_to_avenue(self):
        """Test that 'av' canonicalizes to 'avenue'."""
        from dedupe.preprocess import normalize_street_full
        
        av = pd.Series(["av de lausanne"])
        avenue = pd.Series(["avenue de lausanne"])
        
        av_full = normalize_street_full(av).iloc[0]
        avenue_full = normalize_street_full(avenue).iloc[0]
        
        assert av_full == avenue_full
        assert "avenue" in av_full
    
    def test_french_bd_to_boulevard(self):
        """Test that 'bd' canonicalizes to 'boulevard'."""
        from dedupe.preprocess import normalize_street_full
        
        bd = pd.Series(["bd de grancy"])
        boulevard = pd.Series(["boulevard de grancy"])
        
        bd_full = normalize_street_full(bd).iloc[0]
        boulevard_full = normalize_street_full(boulevard).iloc[0]
        
        assert bd_full == boulevard_full
        assert "boulevard" in bd_full
    
    def test_italian_v_to_via(self):
        """Test that 'v' canonicalizes to 'via'."""
        from dedupe.preprocess import normalize_street_full
        
        v = pd.Series(["v manzoni"])
        via = pd.Series(["via manzoni"])
        
        v_full = normalize_street_full(v).iloc[0]
        via_full = normalize_street_full(via).iloc[0]
        
        assert v_full == via_full
        assert "via" in v_full


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
