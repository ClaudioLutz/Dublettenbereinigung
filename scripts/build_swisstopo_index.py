"""
Build a DuckDB index from the swisstopo address register CSV for fast address normalization.

This script:
1. Reads the swisstopo CSV (amtliches-gebaeudeadressverzeichnis_ch_2056.csv)
2. Extracts and normalizes relevant fields
3. Applies the same normalization logic used in preprocess.py
4. Creates a DuckDB database with indexed columns for fast lookups

Usage:
    python scripts/build_swisstopo_index.py [--input PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pandas as pd
import duckdb
import re
from unidecode import unidecode

# Add parent directory to path to import dedupe modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.preprocess import normalize_street_key, street_signature, parse_house_number, _norm_series


def extract_plz4(zip_label: str) -> str:
    """Extract 4-digit PLZ from ZIP_LABEL field like '6377 Seelisberg'."""
    if not zip_label or not isinstance(zip_label, str):
        return ""
    # Extract leading 4 digits
    match = re.match(r'(\d{4})', zip_label.strip())
    return match.group(1) if match else ""


def extract_ort(zip_label: str) -> str:
    """Extract locality name from ZIP_LABEL field like '6377 Seelisberg'."""
    if not zip_label or not isinstance(zip_label, str):
        return ""
    # Remove leading PLZ and whitespace
    parts = zip_label.strip().split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def normalize_swisstopo_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize swisstopo data using the same logic as preprocess.py.
    
    Args:
        df: Raw swisstopo dataframe
        
    Returns:
        Normalized dataframe with derived fields
    """
    print(f"Processing {len(df):,} records...")
    
    # Extract PLZ and Ort from ZIP_LABEL
    df['plz4'] = df['ZIP_LABEL'].apply(extract_plz4)
    df['ort'] = df['ZIP_LABEL'].apply(extract_ort)
    
    # Normalize street label and house number using same logic as preprocess.py
    street_series = _norm_series(df['STN_LABEL'])
    house_series = _norm_series(df['ADR_NUMBER'])
    
    # Compute derived fields
    df['street_norm'] = street_series
    df['street_key'] = normalize_street_key(street_series)
    df['street_sig'] = street_signature(street_series)
    
    house_num, house_sfx = parse_house_number(house_series)
    df['house_num'] = house_num
    df['house_sfx'] = house_sfx
    
    # Keep relevant columns
    result_df = pd.DataFrame({
        # Keys for joining
        'plz4': df['plz4'],
        'street_key': df['street_key'],
        'street_sig': df['street_sig'],
        'house_num': df['house_num'],
        
        # Reference values to use for normalization
        'street_label': df['STN_LABEL'],
        'adr_number': df['ADR_NUMBER'],
        'ort': df['ort'],
        
        # IDs
        'adr_egaid': df['ADR_EGAID'],
        'bdg_egid': df['BDG_EGID'],
        'com_fosnr': df['COM_FOSNR'],
        'com_name': df['COM_NAME'],
        'com_canton': df['COM_CANTON'],
        
        # Metadata
        'adr_status': df['ADR_STATUS'],
        'adr_official': df['ADR_OFFICIAL'],
    })
    
    return result_df


def build_index(input_csv: Path, output_db: Path, filter_status: bool = True) -> None:
    """
    Build DuckDB index from swisstopo CSV.
    
    Args:
        input_csv: Path to swisstopo CSV file
        output_db: Path to output DuckDB file
        filter_status: If True, only keep 'real' and 'planned' addresses
    """
    print(f"Building swisstopo index from {input_csv}...")
    print(f"Output: {output_db}")
    print()
    
    # Check if input file exists
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")
    
    # Read CSV with proper separator (semicolon for swisstopo)
    print("Reading CSV...")
    df = pd.read_csv(input_csv, sep=';', dtype=str, low_memory=False)
    print(f"Read {len(df):,} records")
    print()
    
    # Filter by status if requested
    if filter_status and 'ADR_STATUS' in df.columns:
        before = len(df)
        df = df[df['ADR_STATUS'].isin(['real', 'planned'])].copy()
        print(f"Filtered to {len(df):,} records (status='real' or 'planned', removed {before - len(df):,})")
        print()
    
    # Normalize data
    normalized_df = normalize_swisstopo_data(df)
    
    # Create DuckDB database
    print(f"Creating DuckDB database at {output_db}...")
    
    # Remove existing database
    if output_db.exists():
        print(f"Removing existing database...")
        output_db.unlink()
    
    # Create connection
    con = duckdb.connect(str(output_db))
    
    # Create table with indexes
    con.execute("""
        CREATE TABLE addresses AS 
        SELECT * FROM normalized_df
    """)
    
    # Create indexes on join keys for fast lookups
    print("Creating indexes...")
    con.execute("CREATE INDEX idx_plz4_street_key_house ON addresses(plz4, street_key, house_num)")
    con.execute("CREATE INDEX idx_plz4_street_sig_house ON addresses(plz4, street_sig, house_num)")
    con.execute("CREATE INDEX idx_plz4 ON addresses(plz4)")
    
    # Get statistics
    stats = con.execute("SELECT COUNT(*), COUNT(DISTINCT plz4) as n_plz FROM addresses").fetchone()
    print()
    print(f"✓ Index built successfully!")
    print(f"  Total records: {stats[0]:,}")
    print(f"  Unique PLZ: {stats[1]:,}")
    print(f"  Database size: {output_db.stat().st_size / 1024 / 1024:.1f} MB")
    
    con.close()


def main():
    parser = argparse.ArgumentParser(
        description="Build DuckDB index from swisstopo address register CSV"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("amtliches-gebaeudeadressverzeichnis_ch_2056.csv/amtliches-gebaeudeadressverzeichnis_ch_2056.csv"),
        help="Path to input swisstopo CSV file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("swisstopo_addresses.duckdb"),
        help="Path to output DuckDB file"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Do not filter by address status (keep all records)"
    )
    
    args = parser.parse_args()
    
    try:
        build_index(args.input, args.output, filter_status=not args.no_filter)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
