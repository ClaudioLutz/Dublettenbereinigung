"""
Swisstopo address normalization module.

Provides address normalization using the official Swiss address register (swisstopo)
to replace messy input addresses with canonical reference representations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import pandas as pd
import duckdb


class SwisstopoAddressNormalizer:
    """
    Address normalizer using swisstopo reference data.
    
    This class provides fast, conservative address normalization by joining
    input addresses against a pre-built DuckDB index of the swisstopo address register.
    
    Matching strategy:
    1. Strict match on (plz4, street_key, house_num)
    2. Fallback match on (plz4, street_sig, house_num) for typo recovery
    3. If multiple matches, prefer official addresses (adr_official=true)
    """
    
    def __init__(self, db_path: str | Path):
        """
        Initialize normalizer with DuckDB index.
        
        Args:
            db_path: Path to DuckDB file created by build_swisstopo_index.py
            
        Raises:
            FileNotFoundError: If database file doesn't exist
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Swisstopo database not found: {self.db_path}\n"
                f"Run 'python scripts/build_swisstopo_index.py' to create it."
            )
        
        # Open connection (keep it open for performance)
        self.con = duckdb.connect(str(self.db_path), read_only=True)
        
        # Verify table exists
        tables = self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        if not any(t[0] == 'addresses' for t in tables):
            raise ValueError(f"Database {self.db_path} does not contain 'addresses' table")
    
    def __del__(self):
        """Close database connection on cleanup."""
        if hasattr(self, 'con') and self.con:
            self.con.close()
    
    def normalize_chunk(self, keys_df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize a chunk of addresses using swisstopo reference data.
        
        Uses a multilingual-safe, type-preserving matching strategy to avoid
        collisions like Augustinergasse ↔ Augustinerhof.
        
        Args:
            keys_df: DataFrame with columns:
                - row_id (int): Row index for joining back
                - plz4 (str): 4-digit postal code
                - street_key (str): Normalized street key (no type tokens) - legacy
                - street_sig (str): Street signature for fuzzy matching - legacy
                - street_full (str): Type-preserving street key (multilingual safe)
                - street_sig_full (str): Type-preserving signature (multilingual safe)
                - house_num (str): House number (numeric part only)
                
        Returns:
            DataFrame with columns:
                - row_id (int): Original row index
                - street_label_ref (str): Canonical street name from swisstopo
                - adr_number_ref (str): Canonical house number from swisstopo
                - plz4_ref (str): Canonical PLZ from swisstopo
                - ort_ref (str): Canonical locality name from swisstopo
                - adr_egaid_ref (str): Address ID from swisstopo
                - bdg_egid_ref (str): Building ID from swisstopo
                - match_type (str): 'strict', 'sig_full', or 'none'
                - candidate_count (int): Number of candidate matches (for ambiguity detection)
                
            Only rows with matches are returned (inner join semantics).
        """
        if keys_df.empty:
            return pd.DataFrame()
        
        # Register the DataFrame with DuckDB
        self.con.register('input_keys', keys_df)
        
        # Pass A: Strict match on (plz4, street_full, house_num) - TYPE-PRESERVING
        # This prevents Augustinergasse ↔ Augustinerhof collisions
        strict_query = """
        WITH candidates AS (
            SELECT 
                i.row_id,
                a.street_label,
                a.adr_number,
                a.plz4,
                a.ort,
                a.adr_egaid,
                a.bdg_egid,
                'strict' as match_type,
                -- Count candidates for ambiguity detection
                COUNT(*) OVER (PARTITION BY i.row_id) AS candidate_count,
                -- Prefer official addresses
                ROW_NUMBER() OVER (
                    PARTITION BY i.row_id 
                    ORDER BY 
                        CASE WHEN a.adr_official = 'true' THEN 0 ELSE 1 END,
                        a.adr_egaid
                ) as rn
            FROM input_keys i
            INNER JOIN addresses a
                ON i.plz4 = a.plz4
                AND i.street_full = a.street_full
                AND i.house_num = a.house_num
            WHERE a.plz4 != ''
                AND a.street_full != ''
                AND a.house_num != ''
        )
        SELECT 
            row_id,
            street_label as street_label_ref,
            adr_number as adr_number_ref,
            plz4 as plz4_ref,
            ort as ort_ref,
            adr_egaid as adr_egaid_ref,
            bdg_egid as bdg_egid_ref,
            match_type,
            candidate_count
        FROM candidates
        WHERE rn = 1
        """
        
        strict_matches = self.con.execute(strict_query).fetchdf()
        
        # If all rows matched strictly, we're done
        if len(strict_matches) == len(keys_df):
            self.con.unregister('input_keys')
            return strict_matches
        
        # Pass B: Signature match on (plz4, street_sig_full, house_num) - TYPE-PRESERVING FUZZY
        # This allows typo recovery while still preventing cross-type collisions
        matched_row_ids = set(strict_matches['row_id'].tolist()) if not strict_matches.empty else set()
        
        sig_query = """
        WITH candidates AS (
            SELECT 
                i.row_id,
                a.street_label,
                a.adr_number,
                a.plz4,
                a.ort,
                a.adr_egaid,
                a.bdg_egid,
                'sig_full' as match_type,
                -- Count candidates for ambiguity detection
                COUNT(*) OVER (PARTITION BY i.row_id) AS candidate_count,
                -- Prefer official addresses
                ROW_NUMBER() OVER (
                    PARTITION BY i.row_id 
                    ORDER BY 
                        CASE WHEN a.adr_official = 'true' THEN 0 ELSE 1 END,
                        a.adr_egaid
                ) as rn
            FROM input_keys i
            INNER JOIN addresses a
                ON i.plz4 = a.plz4
                AND i.street_sig_full = a.street_sig_full
                AND i.house_num = a.house_num
            WHERE a.plz4 != ''
                AND a.street_sig_full != ''
                AND a.house_num != ''
        )
        SELECT 
            row_id,
            street_label as street_label_ref,
            adr_number as adr_number_ref,
            plz4 as plz4_ref,
            ort as ort_ref,
            adr_egaid as adr_egaid_ref,
            bdg_egid as bdg_egid_ref,
            match_type,
            candidate_count
        FROM candidates
        WHERE rn = 1
        """
        
        if matched_row_ids:
            # Exclude already matched rows
            keys_df_remaining = keys_df[~keys_df['row_id'].isin(matched_row_ids)]
            if not keys_df_remaining.empty:
                self.con.register('input_keys_remaining', keys_df_remaining)
                sig_query = sig_query.replace('input_keys', 'input_keys_remaining')
                sig_matches = self.con.execute(sig_query).fetchdf()
                self.con.unregister('input_keys_remaining')
            else:
                sig_matches = pd.DataFrame()
        else:
            sig_matches = self.con.execute(sig_query).fetchdf()
        
        # Unregister input DataFrame
        self.con.unregister('input_keys')
        
        # Combine strict and signature matches
        if strict_matches.empty and sig_matches.empty:
            return pd.DataFrame()
        elif strict_matches.empty:
            return sig_matches
        elif sig_matches.empty:
            return strict_matches
        else:
            return pd.concat([strict_matches, sig_matches], ignore_index=True)
    
    def get_stats(self) -> dict:
        """
        Get statistics about the swisstopo database.
        
        Returns:
            Dictionary with statistics
        """
        stats = {}
        
        # Total records
        result = self.con.execute("SELECT COUNT(*) FROM addresses").fetchone()
        stats['total_records'] = result[0]
        
        # Unique PLZ
        result = self.con.execute("SELECT COUNT(DISTINCT plz4) FROM addresses WHERE plz4 != ''").fetchone()
        stats['unique_plz'] = result[0]
        
        # Official vs non-official
        result = self.con.execute(
            "SELECT adr_official, COUNT(*) FROM addresses GROUP BY adr_official"
        ).fetchall()
        stats['by_official'] = {row[0]: row[1] for row in result}
        
        # By status
        result = self.con.execute(
            "SELECT adr_status, COUNT(*) FROM addresses GROUP BY adr_status"
        ).fetchall()
        stats['by_status'] = {row[0]: row[1] for row in result}
        
        return stats
