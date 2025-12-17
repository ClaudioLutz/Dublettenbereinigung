"""
Highly Optimized Duplicate Checker for 7.5M+ Rows
=================================================

Optimizations:
1. Fully vectorized pandas operations (no iterrows!)
2. Efficient blocking with hash-based grouping
3. Fixed parallel processing with proper serialization
4. Memory-efficient batch processing
5. Early termination strategies
6. NumPy acceleration where possible

Performance target: Process 7.5M rows in minutes, not hours
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Set
import logging
from collections import defaultdict
import re
from unidecode import unidecode
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import time
from dataclasses import dataclass, asdict
import hashlib
from rapidfuzz import fuzz
import pickle
import cologne_phonetics

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MatchResult:
    """Result of a duplicate check between two records"""
    record_a_idx: int
    record_b_idx: int
    confidence_score: float
    match_type: str
    details: Dict

class VectorizedAddressNormalizer:
    """Vectorized operations for address normalization"""
    
    @staticmethod
    def normalize_plz_vectorized(plz_series: pd.Series) -> pd.Series:
        """Vectorized PLZ normalization"""
        # Convert to string, remove non-digits, pad to 5 digits
        return (plz_series
                .fillna('')
                .astype(str)
                .str.replace(r'\D', '', regex=True)
                .str.zfill(5)
                .str[:5])
    
    @staticmethod
    def normalize_street_vectorized(street_series: pd.Series) -> pd.Series:
        """Vectorized street normalization"""
        # Fill NA, convert to string, lowercase
        streets = street_series.fillna('').astype(str).str.strip().str.lower()
        
        # Replace common German street suffixes
        suffix_map = {
            'str.': 'strasse', 'straße': 'strasse', 'str': 'strasse',
            'weg': 'weg', 'allee': 'allee', 'platz': 'platz',
            'gasse': 'gasse', 'ring': 'ring'
        }
        
        for old, new in suffix_map.items():
            streets = streets.str.replace(f'{old}$', new, regex=True)
        
        # Remove house numbers (end of string)
        streets = streets.str.replace(r'\s+\d+[a-z]*$', '', regex=True)
        streets = streets.str.replace(r'^\d+[a-z]*\s+', '', regex=True)
        
        # Handle umlauts
        streets = streets.str.replace('ß', 'ss')
        
        # Apply unidecode vectorized
        streets = streets.apply(lambda x: unidecode(x) if x else '')
        
        # Remove special chars and extra whitespace
        streets = streets.str.replace(r'[^a-z\s]', '', regex=True)
        streets = streets.str.replace(r'\s+', ' ', regex=True).str.strip()
        
        return streets
    
    @staticmethod
    def normalize_name_vectorized(name_series: pd.Series) -> pd.Series:
        """Vectorized name normalization"""
        names = name_series.fillna('').astype(str).str.strip().str.lower()
        names = names.str.replace('ß', 'ss')
        names = names.apply(lambda x: unidecode(x) if x else '')
        names = names.str.replace(r'\s+', ' ', regex=True).str.strip()
        return names

def normalize_street(street):
    """Normalize street name for comparison"""
    if pd.isna(street) or not str(street).strip():
        return ''

    street = str(street).strip().lower()

    # Apply normalization rules (reuse from VectorizedAddressNormalizer)
    # 1. Replace special characters
    street = street.replace('ß', 'ss')
    street = street.replace('ä', 'ae')
    street = street.replace('ö', 'oe')
    street = street.replace('ü', 'ue')

    # 2. Remove punctuation
    street = street.replace('.', '').replace(',', '').replace('-', ' ')

    # 3. Normalize common abbreviations
    abbreviations = {
        'str': 'strasse',
        'strasse': 'strasse',
        'weg': 'weg',
        'platz': 'platz',
        'allee': 'allee',
        'gasse': 'gasse'
    }

    for abbr, full in abbreviations.items():
        if street.endswith(abbr):
            street = street[:-len(abbr)] + full
            break # Only apply one suffix

    # 4. Remove extra whitespace
    street = ' '.join(street.split())

    return street

def normalize_plz_scalar(plz):
    """Normalize PLZ scalar safely handling floats"""
    if pd.isna(plz):
        return ''
    s = str(plz).strip()
    if s.endswith('.0'):
        return s[:-2]
    return s

def compute_normalized_address_ratio_fast(record_a, record_b):
    """Fast normalized address ratio computation using precomputed fields"""

    # Use precomputed normalized fields
    street_a = record_a.get('street_normalized', '')
    street_b = record_b.get('street_normalized', '')
    plz_a = record_a.get('plz_normalized', '')
    plz_b = record_b.get('plz_normalized', '')

    # PLZ comparison (exact match)
    plz_ratio = 1.0 if plz_a and plz_b and plz_a == plz_b else 0.0

    # Street comparison (fuzzy match)
    if street_a and street_b:
        street_ratio = fuzz.ratio(street_a, street_b) / 100.0
    else:
        street_ratio = 0.0

    # Weighted combination (PLZ is more discriminative)
    # Require at least one component to be present
    if plz_a or street_a:
        address_ratio = 0.6 * plz_ratio + 0.4 * street_ratio
    else:
        address_ratio = 0.0

    return address_ratio

def determine_address_assisted_match_type(is_swapped, has_phonetic):
    """Determine match type for address-assisted matches"""
    if is_swapped:
        return 'address_assisted_swapped'
    else:
        return 'address_assisted_normal'

def calculate_address_assisted_confidence(match_type, address_ratio):
    """Calculate confidence for address-assisted matches"""

    if match_type == 'address_assisted_normal':
        # Base confidence 70, bonus up to 10
        confidence = 70 + address_ratio * 10
        # Range: 70-80 (requires address_ratio >= 0.75)

    elif match_type == 'address_assisted_swapped':
        # Small penalty for swapped names
        confidence = 68 + address_ratio * 10
        # Range: 68-78

    else:
        # Fallback (shouldn't happen)
        confidence = 70

    return round(confidence, 2)

def get_cologne_phonetic(name: str) -> str:
    """
    Get Cologne Phonetic code for a name safely.
    Returns empty string if encoding fails or name is empty.
    """
    if pd.isna(name) or not str(name).strip():
        return ''
    try:
        result = cologne_phonetics.encode(str(name).strip())
        if result and len(result) > 0:
            # cologne_phonetics.encode returns list of tuples: [('name', 'code')]
            return result[0][1]
    except:
        pass
    return ''

class OptimizedBlockingStrategy:
    """Highly optimized blocking strategy using vectorized operations"""
    
    def __init__(self):
        self.normalizer = VectorizedAddressNormalizer()
    
    def create_blocking_keys_vectorized(self, df: pd.DataFrame) -> pd.Series:
        """Create blocking keys using fully vectorized operations"""
        # Normalize PLZ and Street in batch
        plz_norm = self.normalizer.normalize_plz_vectorized(df['Plz'])
        street_norm = self.normalizer.normalize_street_vectorized(df['Strasse'])
        
        # Create conditions for different blocking strategies
        has_both = (plz_norm != '') & (street_norm != '')
        has_plz_only = (plz_norm != '') & (street_norm == '')
        has_street_only = (plz_norm == '') & (street_norm != '')
        
        # Vectorized key creation
        blocking_keys = pd.Series('no_address', index=df.index)
        blocking_keys[has_both] = plz_norm[has_both] + '_' + street_norm[has_both]
        blocking_keys[has_plz_only] = 'plz_only_' + plz_norm[has_plz_only]
        blocking_keys[has_street_only] = 'street_only_' + street_norm[has_street_only]
        
        return blocking_keys
    
    def create_blocks(self, df: pd.DataFrame, max_block_size: int = 10000) -> Dict[str, pd.DataFrame]:
        """Create blocks efficiently using groupby"""
        logger.info(f"Creating blocks for {len(df)} records...")
        start_time = time.time()
        
        # Create blocking keys vectorized
        blocking_keys = self.create_blocking_keys_vectorized(df)
        
        # Add to dataframe
        df_with_keys = df.copy()
        df_with_keys['blocking_key'] = blocking_keys
        
        # Group by blocking key efficiently
        grouped = df_with_keys.groupby('blocking_key')
        
        # Filter blocks by size
        blocks = {}
        total_records = 0
        skipped_blocks = 0
        
        for key, group_df in grouped:
            block_size = len(group_df)
            if 1 < block_size <= max_block_size:  # Only blocks with 2+ records, not too large
                blocks[key] = group_df.reset_index(drop=False)  # Keep original index
                total_records += block_size
            elif block_size > max_block_size:
                # Split large blocks into smaller chunks
                for i in range(0, block_size, max_block_size):
                    chunk = group_df.iloc[i:i+max_block_size]
                    if len(chunk) > 1:
                        blocks[f"{key}_chunk_{i}"] = chunk.reset_index(drop=False)
                        total_records += len(chunk)
                skipped_blocks += 1
        
        elapsed = time.time() - start_time
        logger.info(f"Created {len(blocks)} blocks in {elapsed:.2f}s")
        logger.info(f"Average block size: {total_records/len(blocks):.1f} records")
        if skipped_blocks > 0:
            logger.info(f"Split {skipped_blocks} oversized blocks")
        
        # Calculate comparison reduction
        original_comparisons = len(df) * (len(df) - 1) // 2
        blocked_comparisons = sum(len(b) * (len(b) - 1) // 2 for b in blocks.values())
        reduction = (1 - blocked_comparisons / original_comparisons) * 100 if original_comparisons > 0 else 0
        logger.info(f"Comparison reduction: {reduction:.1f}% ({original_comparisons:,} -> {blocked_comparisons:,})")
        
        return blocks

class PhoneticBlockingStrategy(OptimizedBlockingStrategy):
    """Enhanced blocking strategy with phonetic codes for German names"""
    
    def create_blocking_keys_vectorized(self, df: pd.DataFrame) -> pd.Series:
        """Create blocking keys with phonetic fallback for no_address records"""
        # Get standard address-based blocking keys
        standard_keys = super().create_blocking_keys_vectorized(df)
        
        # Pre-compute phonetic codes (vectorized)
        logger.info("Computing phonetic codes for names...")
        df['vorname_phon'] = df['Vorname'].apply(get_cologne_phonetic)
        df['name_phon'] = df['Name'].apply(get_cologne_phonetic)
        
        # Create phonetic blocking keys only for "no_address" records
        phonetic_keys = pd.Series('no_phonetic', index=df.index)
        no_address_mask = standard_keys == 'no_address'
        
        if no_address_mask.any():
            # Only create phonetic keys for records without address data
            phonetic_keys[no_address_mask] = (
                'phon_' + 
                df.loc[no_address_mask, 'vorname_phon'] + '_' + 
                df.loc[no_address_mask, 'name_phon']
            )
            logger.info(f"Created phonetic blocking keys for {no_address_mask.sum()} records without address")
        
        # Use phonetic blocking for no_address records, standard for others
        combined_keys = standard_keys.copy()
        combined_keys[no_address_mask] = phonetic_keys[no_address_mask]
        
        return combined_keys

class MultiPassBlockingStrategy(PhoneticBlockingStrategy):
    """Multi-pass blocking: Pass A (address) + Pass B (phonetic+year) for targeted records"""

    def __init__(self, max_block_size: int = 1000):
        super().__init__()
        self.max_block_size = max_block_size
        self.pass_b_generated = 0  # Track statistics

    def _extract_year(self, date_val):
        """Extract year from date value (string or object)"""
        try:
            if pd.isna(date_val) or date_val == '':
                return None

            if isinstance(date_val, str):
                # Try YYYY-MM-DD or DD.MM.YYYY
                match = re.search(r'(\d{4})', date_val)
                if match:
                    return int(match.group(1))
            elif hasattr(date_val, 'year'):
                return date_val.year
            elif isinstance(date_val, (int, float)):
                return int(date_val)
        except:
            pass
        return None

    def _create_pass_b_key(self, vorname_phon, name_phon, year):
        """Create Pass-B key: passB_{min_phon}_{max_phon}_{year}"""
        # Use min/max to handle name swaps automatically
        if not vorname_phon or not name_phon or pd.isna(year):
            return None

        phon_min = min(vorname_phon, name_phon)
        phon_max = max(vorname_phon, name_phon)

        return f"passB_{phon_min}_{phon_max}_{int(year)}"

    def create_blocking_keys_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create blocking keys with selective Pass-B generation"""

        # Get Pass-A keys from parent class (includes phonetic for no_address)
        # This returns a Series
        pass_a_keys = super().create_blocking_keys_vectorized(df)

        # Ensure phonetic codes are computed (parent may have done this, but we need to be sure)
        if 'vorname_phon' not in df.columns:
            logger.info("Computing phonetic codes for Pass-B...")
            df['vorname_phon'] = df['Vorname'].apply(get_cologne_phonetic)
            df['name_phon'] = df['Name'].apply(get_cologne_phonetic)

        # Compute effective birth year (prefer Geburtstag, fallback to Jahrgang)
        # Vectorized year extraction would be better but iterating is safer for mixed types
        df['effective_year'] = df.apply(
            lambda row: self._extract_year(row['Geburtstag'])
                        if self._extract_year(row['Geburtstag']) is not None
                        else self._extract_year(row.get('Jahrgang')),
            axis=1
        )

        # Identify records that need Pass-B keys
        # Criteria: standard_key starts with 'plz_only_', 'street_only_', or 'phon_' AND effective_year is present
        needs_pass_b = (
            (pass_a_keys.str.startswith('plz_only_') |
             pass_a_keys.str.startswith('street_only_') |
             pass_a_keys.str.startswith('phon_') |
             pass_a_keys.str.startswith('no_address')) & # Handle no_address (should become phon_ but just in case)
            (df['effective_year'].notna())
        )

        # Create result DataFrame with Pass-A keys
        # We need to preserve the original index
        result_df = pd.DataFrame({
            'original_index': df.index,
            'blocking_key': pass_a_keys,
            'blocking_pass': 'A'
        })

        # Generate Pass-B keys for selected records
        if needs_pass_b.any():
            pass_b_records = df[needs_pass_b].copy()

            # Create Pass-B blocking keys
            pass_b_keys = pass_b_records.apply(
                lambda row: self._create_pass_b_key(
                    row['vorname_phon'],
                    row['name_phon'],
                    row['effective_year']
                ),
                axis=1
            )

            # Filter out None keys (if any failed)
            valid_pass_b = pass_b_keys.notna()
            if valid_pass_b.any():
                pass_b_df = pd.DataFrame({
                    'original_index': pass_b_records[valid_pass_b].index,
                    'blocking_key': pass_b_keys[valid_pass_b],
                    'blocking_pass': 'B'
                })

                # Concatenate Pass-A and Pass-B keys
                result_df = pd.concat([result_df, pass_b_df], ignore_index=True)

                self.pass_b_generated = len(pass_b_df)
                logger.info(f"Generated {self.pass_b_generated} Pass-B keys")

        return result_df

    def _handle_large_block(self, block_key, block_df, max_size=1000):
        """Sub-block deterministically instead of arbitrary chunking"""
        if len(block_df) <= max_size:
            return [(block_key, block_df)]

        sub_blocks = []

        # Determine sub-blocking strategy based on key type
        if block_key.startswith('street_only_'):
            # Sub-block by year
            # Ensure effective_year is in block_df
            if 'effective_year' not in block_df.columns:
                 block_df['effective_year'] = block_df.apply(
                    lambda row: self._extract_year(row['Geburtstag'])
                                if self._extract_year(row['Geburtstag']) is not None
                                else self._extract_year(row.get('Jahrgang')),
                    axis=1
                )

            for year, year_df in block_df.groupby('effective_year'):
                if pd.notna(year):
                    year_key = f"{block_key}_year_{int(year)}"
                    if len(year_df) <= max_size:
                        sub_blocks.append((year_key, year_df))
                    else:
                        # Further sub-block by first letter of Name
                        self._sub_block_by_letter(year_key, year_df, sub_blocks, max_size)
                else:
                    self._sub_block_by_letter(f"{block_key}_noyear", year_df, sub_blocks, max_size)

            return sub_blocks

        elif block_key.startswith('passB_'):
            # Already has year, sub-block by first letter
            self._sub_block_by_letter(block_key, block_df, sub_blocks, max_size)
            return sub_blocks

        else:
            # Fall back to current chunking for other types
            if len(block_df) > max_size:
                 self._sub_block_by_letter(block_key, block_df, sub_blocks, max_size)
            else:
                return [(block_key, block_df)]

        # If still empty, return chunks
        if not sub_blocks:
             return self._chunk_block(block_key, block_df, max_size)

        return sub_blocks

    def _sub_block_by_letter(self, base_key, df, sub_blocks_list, max_size):
        """Helper to sub-block by first letter of Name"""
        # Create a temporary column for first letter
        first_letters = df['Name'].fillna('').astype(str).str[0].str.upper()

        for letter, letter_df in df.groupby(first_letters):
            if not letter: continue # Skip empty

            letter_key = f"{base_key}_L_{letter}"
            if len(letter_df) <= max_size:
                sub_blocks_list.append((letter_key, letter_df))
            else:
                # If still too large, fallback to chunking
                chunks = self._chunk_block(letter_key, letter_df, max_size)
                sub_blocks_list.extend(chunks)

    def _chunk_block(self, block_key, block_df, max_size):
        """Fallback to arbitrary chunking"""
        chunks = []
        block_size = len(block_df)
        for i in range(0, block_size, max_size):
            chunk = block_df.iloc[i:i+max_size]
            if len(chunk) > 1:
                chunks.append((f"{block_key}_chunk_{i}", chunk))
        return chunks

    def create_blocks(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Override create_blocks to handle Multi-Pass logic"""
        logger.info(f"Creating Multi-Pass blocks for {len(df)} records...")
        start_time = time.time()

        # Generate keys (DataFrame with original_index)
        keys_df = self.create_blocking_keys_vectorized(df)

        # Group keys_df by blocking_key
        grouped = keys_df.groupby('blocking_key')

        blocks = {}
        total_records_in_blocks = 0

        for key, group in grouped:
            # Get the original indices for this block
            indices = group['original_index'].values

            # Extract the subset from original df
            block_df = df.loc[indices].copy()

            # Ensure we keep the original index as a column 'index'
            block_df = block_df.reset_index(drop=False)
            # if 'index' is already there, it means reset_index put the index into 'index'

            # Handle large blocks
            sub_blocks = self._handle_large_block(key, block_df, self.max_block_size)

            for sub_key, sub_df in sub_blocks:
                if len(sub_df) > 1:
                    blocks[sub_key] = sub_df
                    total_records_in_blocks += len(sub_df)

        elapsed = time.time() - start_time
        logger.info(f"Created {len(blocks)} blocks (Pass A & B) in {elapsed:.2f}s")

        return blocks

class FastBusinessRules:
    """Optimized business rules engine"""
    
    @staticmethod
    def extract_year(date_str):
        """Extract year from date string"""
        if pd.isna(date_str) or date_str is None or str(date_str).strip() == '':
            return None
        try:
            date_str = str(date_str).strip()
            match = re.search(r'(\d{4})', date_str)
            if match:
                return int(match.group(1))
        except:
            pass
        return None
    
    @staticmethod
    def check_zweitname(name_a, name2_a, name_b, name2_b) -> bool:
        """
        Check Zweitname rule with compound surname support
        
        Handles cases where name2 might be the suffix of name:
        - name="Rohner-Stassek", name2="" 
        - name="Rohner", name2="-Stassek"
        Should match!
        
        Returns True if records pass the Zweitname rule, False otherwise.
        """
        # Normalize all fields
        norm_name_a = str(name_a).strip().lower() if not pd.isna(name_a) else ''
        norm_name2_a = str(name2_a).strip().lower() if not pd.isna(name2_a) else ''
        norm_name_b = str(name_b).strip().lower() if not pd.isna(name_b) else ''
        norm_name2_b = str(name2_b).strip().lower() if not pd.isna(name2_b) else ''
        
        # Case 1: Both name2 fields populated - must match exactly
        if norm_name2_a and norm_name2_b:
            return norm_name2_a == norm_name2_b
        
        # Case 2: Both name2 fields empty - pass
        if not norm_name2_a and not norm_name2_b:
            return True
        
        # Case 3: One name2 populated, one empty - check if it's a suffix of the other's name
        if norm_name2_a and not norm_name2_b:
            # Check if name2_a matches the ending of name_b
            return norm_name_b.endswith(norm_name2_a)
        
        if norm_name2_b and not norm_name2_a:
            # Check if name2_b matches the ending of name_a
            return norm_name_a.endswith(norm_name2_b)
        
        return True
    
    @staticmethod
    def check_date_rule(geburtstag_a, jahrgang_a, geburtstag_b, jahrgang_b) -> bool:
        """Check date matching rules"""
        year_a = FastBusinessRules.extract_year(geburtstag_a)
        year_b = FastBusinessRules.extract_year(geburtstag_b)
        
        # Parse Jahrgang
        jg_a = None
        jg_b = None
        try:
            if not pd.isna(jahrgang_a) and str(jahrgang_a).strip():
                jg_a = int(float(str(jahrgang_a).strip()))
        except:
            pass
        try:
            if not pd.isna(jahrgang_b) and str(jahrgang_b).strip():
                jg_b = int(float(str(jahrgang_b).strip()))
        except:
            pass
        
        # Effective year: birth date year takes precedence
        effective_a = year_a if year_a else jg_a
        effective_b = year_b if year_b else jg_b
        
        if effective_a and effective_b:
            return effective_a == effective_b
        elif effective_a is None and effective_b is None:
            return True
        else:
            return False

class OptimizedFuzzyMatcher:
    """Optimized fuzzy matching"""
    
    @staticmethod
    def normalize_name(name):
        """
        Fast name normalization with German umlaut handling
        
        Handles German umlauts where:
        - ü/Ü can be written as ue/Ue
        - ä/Ä can be written as ae/Ae  
        - ö/Ö can be written as oe/Oe
        
        Both forms are normalized to the same result for consistent matching.
        """
        if pd.isna(name):
            return ""
        name = str(name).strip().lower()
        
        # Replace ß with ss (German eszett)
        name = name.replace('ß', 'ss')
        
        # Normalize German umlauts to their ASCII equivalents BEFORE unidecode
        # This ensures both "Müller" and "Mueller" normalize to "mueller"
        name = name.replace('ü', 'ue')
        name = name.replace('ä', 'ae')
        name = name.replace('ö', 'oe')
        
        # Apply unidecode for any remaining accents/diacritics
        name = unidecode(name)
        
        # Clean up whitespace
        return re.sub(r'\s+', ' ', name).strip()
    
    @staticmethod
    def compare_names(vorname_a, name_a, vorname_b, name_b) -> Dict:
        """Compare names with swapping detection"""
        # Normalize
        v_a = OptimizedFuzzyMatcher.normalize_name(vorname_a)
        n_a = OptimizedFuzzyMatcher.normalize_name(name_a)
        v_b = OptimizedFuzzyMatcher.normalize_name(vorname_b)
        n_b = OptimizedFuzzyMatcher.normalize_name(name_b)
        
        if not v_a or not n_a or not v_b or not n_b:
            return {'best_score': 0, 'is_swapped': False, 'normal_score': 0, 'swapped_score': 0}
        
        # Normal comparison
        normal_v = fuzz.QRatio(v_a, v_b) / 100.0
        normal_n = fuzz.QRatio(n_a, n_b) / 100.0
        normal_score = (normal_v + normal_n) / 2
        
        # Swapped comparison
        swapped_v = fuzz.QRatio(v_a, n_b) / 100.0
        swapped_n = fuzz.QRatio(n_a, v_b) / 100.0
        swapped_score = (swapped_v + swapped_n) / 2
        
        return {
            'normal_score': normal_score,
            'swapped_score': swapped_score,
            'best_score': max(normal_score, swapped_score),
            'is_swapped': swapped_score > normal_score,
            'normal_vorname_sim': normal_v,
            'normal_name_sim': normal_n,
            'swapped_vorname_sim': swapped_v,
            'swapped_name_sim': swapped_n
        }

def process_block_worker(args: Tuple) -> List[Dict]:
    """
    Worker function for parallel block processing with two-stage architecture
    
    Stage 1: Exact match detection (normalized names, both normal and swapped)
    Stage 2: Fuzzy match for remaining unmatched records
    
    Returns list of match dictionaries (not MatchResult objects for serialization)
    """
    # Unpack arguments (handle optional block_key for backward compatibility/flexibility)
    if len(args) == 4:
        block_key, block_data, confidence_threshold, fuzzy_threshold = args
    else:
        block_data, confidence_threshold, fuzzy_threshold = args
        block_key = "unknown"

    # Determine blocking pass
    blocking_pass = 'A'
    if isinstance(block_key, str) and ('passB_' in block_key or '_passB_' in block_key):
        blocking_pass = 'B'
    
    matches = []
    block_size = len(block_data)
    
    if block_size < 2:
        return matches
    
    # Convert to records for faster access
    records = block_data.to_dict('records')
    original_indices = block_data['index'].values
    
    # Track matched indices to skip in Stage 2
    matched_indices = set()
    
    # =======================
    # STAGE 1: EXACT MATCHING
    # =======================
    for i in range(block_size):
        for j in range(i + 1, block_size):
            record_a = records[i]
            record_b = records[j]
            
            # Check business rules first (fast rejection)
            if not FastBusinessRules.check_zweitname(
                record_a.get('Name'), record_a.get('Name2'),
                record_b.get('Name'), record_b.get('Name2')
            ):
                continue
            
            if not FastBusinessRules.check_date_rule(
                record_a.get('Geburtstag'), record_a.get('Jahrgang'),
                record_b.get('Geburtstag'), record_b.get('Jahrgang')
            ):
                continue
            
            # Normalize names for exact comparison
            v_a_norm = OptimizedFuzzyMatcher.normalize_name(record_a.get('Vorname', ''))
            n_a_norm = OptimizedFuzzyMatcher.normalize_name(record_a.get('Name', ''))
            v_b_norm = OptimizedFuzzyMatcher.normalize_name(record_b.get('Vorname', ''))
            n_b_norm = OptimizedFuzzyMatcher.normalize_name(record_b.get('Name', ''))
            
            # Skip if any name is empty
            if not (v_a_norm and n_a_norm and v_b_norm and n_b_norm):
                continue
            
            # Check both normal and swapped exact matches
            is_exact_normal = (v_a_norm == v_b_norm and n_a_norm == n_b_norm)
            is_exact_swapped = (v_a_norm == n_b_norm and n_a_norm == v_b_norm)
            
            if is_exact_normal or is_exact_swapped:
                # Calculate address match ratio for confidence scoring
                address_fields = ['Strasse', 'HausNummer', 'Plz', 'Ort']
                address_matches = 0
                total_address_fields = 0
                
                for field in address_fields:
                    val_a = str(record_a.get(field, '')).strip().lower()
                    val_b = str(record_b.get(field, '')).strip().lower()
                    
                    if val_a and val_b:
                        total_address_fields += 1
                        if val_a == val_b:
                            address_matches += 1
                
                address_ratio = address_matches / max(total_address_fields, 1)
                
                # Exact match confidence: 90-100% based on address matches
                # Normal exact: 90-100%
                # Swapped exact: 85-95% (slightly lower due to name swap)
                if is_exact_normal:
                    confidence = 90 + (address_ratio * 10)  # 90-100%
                    match_type = 'exact_normal'
                else:  # is_exact_swapped
                    confidence = 85 + (address_ratio * 10)  # 85-95%
                    match_type = 'exact_swapped'
                
                matches.append({
                    'record_a_idx': int(original_indices[i]),
                    'record_b_idx': int(original_indices[j]),
                    'confidence_score': float(confidence),
                    'match_type': match_type,
                    'details': {
                        'address_ratio': address_ratio,
                        'address_matches': address_matches,
                        'total_address_fields': total_address_fields,
                        'blocking_pass': blocking_pass,
                        'block_key': block_key
                    }
                })
                
                # Mark as matched to skip in Stage 2
                matched_indices.add(i)
                matched_indices.add(j)
    
    # Precompute normalized address fields (once per record)
    block_data['street_normalized'] = block_data['Strasse'].apply(normalize_street)
    block_data['plz_normalized'] = block_data['Plz'].apply(normalize_plz_scalar)

    # Update records with new fields
    records = block_data.to_dict('records')

    # =======================
    # STAGE 2: FUZZY MATCHING
    # =======================
    for i in range(block_size):
        # Skip if already matched in Stage 1
        if i in matched_indices:
            continue
            
        for j in range(i + 1, block_size):
            # Skip if already matched in Stage 1
            if j in matched_indices:
                continue
            
            record_a = records[i]
            record_b = records[j]
            
            # Check business rules first (fast rejection)
            if not FastBusinessRules.check_zweitname(
                record_a.get('Name'), record_a.get('Name2'),
                record_b.get('Name'), record_b.get('Name2')
            ):
                continue
            
            if not FastBusinessRules.check_date_rule(
                record_a.get('Geburtstag'), record_a.get('Jahrgang'),
                record_b.get('Geburtstag'), record_b.get('Jahrgang')
            ):
                continue
            
            # Fuzzy name matching
            name_results = OptimizedFuzzyMatcher.compare_names(
                record_a.get('Vorname', ''), record_a.get('Name', ''),
                record_b.get('Vorname', ''), record_b.get('Name', '')
            )
            
            best_score = name_results['best_score']
            is_swapped = name_results['is_swapped']

            # Check if name similarity meets threshold
            if best_score < fuzzy_threshold:
                # NEW: Address-aware gate for borderline name scores
                # Also handles Phonetic fallback within this block or separately?
                # The requirements say: "Check address before rejecting" if 0.60 <= best_score < fuzzy_threshold

                # Check for phonetic match (if needed for fallback)
                # We need phonetic info for both address-assisted (as arg) and fallback
                has_phonetic_match = False
                phonetic_match_swapped = False

                # Only compute phonetic if we are in the borderline range
                if 0.60 <= best_score < fuzzy_threshold:
                    # Check for address-assisted match first
                    # Compute normalized address ratio (using precomputed fields)
                    norm_address_ratio = compute_normalized_address_ratio_fast(record_a, record_b)

                    if norm_address_ratio >= 0.75:
                        # Strong address match -> create "address_assisted" match
                        match_type = determine_address_assisted_match_type(is_swapped, False) # phonetic arg not used for type string
                        confidence = calculate_address_assisted_confidence(match_type, norm_address_ratio)

                        matches.append({
                            'record_a_idx': int(original_indices[i]),
                            'record_b_idx': int(original_indices[j]),
                            'confidence_score': float(confidence),
                            'match_type': match_type,
                            'details': {
                                'name_results': name_results,
                                'address_ratio': norm_address_ratio, # Use normalized ratio here
                                'blocking_pass': blocking_pass,
                                'block_key': block_key
                            }
                        })
                        continue # Pair handled, move to next

                    # If address is not strong enough, check phonetic fallback
                    # Compute phonetic codes
                    v_a_phon = get_cologne_phonetic(record_a.get('Vorname', ''))
                    n_a_phon = get_cologne_phonetic(record_a.get('Name', ''))
                    v_b_phon = get_cologne_phonetic(record_b.get('Vorname', ''))
                    n_b_phon = get_cologne_phonetic(record_b.get('Name', ''))
                    
                    # Check phonetic match (normal and swapped)
                    phonetic_match_normal = (v_a_phon and n_a_phon and v_b_phon and n_b_phon and
                                            v_a_phon == v_b_phon and n_a_phon == n_b_phon)
                    phonetic_match_swapped = (v_a_phon and n_a_phon and v_b_phon and n_b_phon and
                                             v_a_phon == n_b_phon and n_a_phon == v_b_phon)
                    
                    if phonetic_match_normal or phonetic_match_swapped:
                        # Boost score above threshold and mark as phonetic-assisted
                        name_results['best_score'] = 0.72  # Just above 0.70 threshold
                        name_results['is_swapped'] = phonetic_match_swapped
                        name_results['phonetic_assisted'] = True
                        # Continue with normal match creation flow
                    else:
                        # No phonetic match and weak address - skip this comparison
                        continue
                else:
                    # Below 60% - too weak even with phonetic
                    continue
            
            # Calculate address match ratio
            address_fields = ['Strasse', 'HausNummer', 'Plz', 'Ort']
            address_matches = 0
            total_address_fields = 0
            
            for field in address_fields:
                val_a = str(record_a.get(field, '')).strip().lower()
                val_b = str(record_b.get(field, '')).strip().lower()
                
                if val_a and val_b:
                    total_address_fields += 1
                    if val_a == val_b:
                        address_matches += 1
            
            address_ratio = address_matches / max(total_address_fields, 1)
            
            # Calculate fuzzy match confidence
            # Check if this is a phonetic-assisted match
            if name_results.get('phonetic_assisted', False):
                # Phonetic-assisted match confidence
                if name_results['is_swapped']:
                    # Phonetic assisted swapped: 70-80% range
                    confidence = 70 + (address_ratio * 10)
                    match_type = 'phonetic_assisted_swapped'
                else:
                    # Phonetic assisted normal: 72-82% range
                    confidence = 72 + (address_ratio * 10)
                    match_type = 'phonetic_assisted_normal'
            else:
                # Regular fuzzy match confidence
                # Base: name similarity * 50 (max 50 points from names)
                # Address bonus: address_ratio * 30 (max 30 points from address)
                # Swap penalty: -5 points if swapped (name swap is more suspicious)
                base_confidence = name_results['best_score'] * 50
                address_bonus = address_ratio * 30
                
                if name_results['is_swapped']:
                    # Fuzzy swapped: 65-85% range (slightly lower due to swap)
                    # Apply small penalty for swap
                    confidence = base_confidence + address_bonus - 5
                    match_type = 'fuzzy_swapped'
                else:
                    # Fuzzy normal: 70-90% range
                    confidence = base_confidence + address_bonus
                    match_type = 'fuzzy_normal'
                
                # Cap fuzzy matches at 95% (never higher than exact matches)
                confidence = min(confidence, 95)
            
            if confidence >= confidence_threshold:
                matches.append({
                    'record_a_idx': int(original_indices[i]),
                    'record_b_idx': int(original_indices[j]),
                    'confidence_score': float(confidence),
                    'match_type': match_type,
                    'details': {
                        'name_results': name_results,
                        'address_ratio': address_ratio,
                        'address_matches': address_matches,
                        'total_address_fields': total_address_fields,
                        'blocking_pass': blocking_pass,
                        'block_key': block_key
                    }
                })
    
    return matches

class UltraFastDuplicateChecker:
    """Ultra-optimized duplicate checker for millions of records with phonetic matching"""
    
    def __init__(self, fuzzy_threshold: float = 0.8, use_parallel: bool = True, n_workers: Optional[int] = None, use_phonetic: bool = True, use_multipass: bool = True):
        self.fuzzy_threshold = fuzzy_threshold
        self.use_parallel = use_parallel
        self.n_workers = n_workers or max(1, mp.cpu_count() - 1)
        self.use_phonetic = use_phonetic
        self.use_multipass = use_multipass
        
        # Select blocking strategy
        if use_multipass:
            self.blocking = MultiPassBlockingStrategy()
            logger.info("Multi-pass blocking enabled (Pass A + Pass B)")
        elif use_phonetic:
            self.blocking = PhoneticBlockingStrategy()
            logger.info("Phonetic matching enabled (Cologne Phonetic)")
        else:
            self.blocking = OptimizedBlockingStrategy()
            logger.info("Phonetic matching disabled")
        
        logger.info(f"Initialized with {self.n_workers} workers, parallel={'enabled' if use_parallel else 'disabled'}")
    
    def _deduplicate_pairs(self, matches: List[Dict]) -> List[Dict]:
        """Remove duplicate pairs, keeping higher confidence match"""
        if not matches:
            return []

        matches_df = pd.DataFrame(matches)

        # Sort by confidence (descending)
        matches_df = matches_df.sort_values('confidence_score', ascending=False)

        # Create pair identifier (sorted to handle A-B vs B-A)
        # Using record indices for pair id
        matches_df['pair_id'] = matches_df.apply(
            lambda row: tuple(sorted([row['record_a_idx'], row['record_b_idx']])),
            axis=1
        )

        original_count = len(matches_df)

        # Keep first occurrence (highest confidence)
        deduplicated = matches_df.drop_duplicates(subset=['pair_id'], keep='first')

        deduplicated_count = original_count - len(deduplicated)
        if deduplicated_count > 0:
            logger.info(f"Removed {deduplicated_count} duplicate pairs (kept highest confidence)")

        return deduplicated.to_dict('records')

    def analyze_duplicates(self, df: pd.DataFrame, confidence_threshold: float = 70.0) -> List[MatchResult]:
        """
        Main analysis function - highly optimized for large datasets
        """
        logger.info(f"Starting duplicate analysis on {len(df):,} records")
        start_time = time.time()
        
        # Create blocks
        blocks = self.blocking.create_blocks(df)
        
        if not blocks:
            logger.warning("No blocks created - no duplicates found")
            return []
        
        logger.info(f"Processing {len(blocks)} blocks...")
        
        # Prepare block data for workers
        block_args = [
            (key, block_df, confidence_threshold, self.fuzzy_threshold)
            for key, block_df in blocks.items()
        ]
        
        all_matches = []
        
        if self.use_parallel and len(blocks) > 10:
            # Parallel processing
            logger.info(f"Using parallel processing with {self.n_workers} workers")
            
            with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
                futures = {executor.submit(process_block_worker, args): i 
                          for i, args in enumerate(block_args)}
                
                completed = 0
                for future in as_completed(futures):
                    try:
                        block_matches = future.result()
                        all_matches.extend(block_matches)
                        completed += 1
                        
                        if completed % 100 == 0 or completed == len(futures):
                            logger.info(f"Processed {completed}/{len(futures)} blocks, found {len(all_matches)} matches so far")
                    except Exception as e:
                        logger.error(f"Error processing block: {e}")
        else:
            # Sequential processing
            logger.info("Using sequential processing")
            for i, args in enumerate(block_args):
                try:
                    block_matches = process_block_worker(args)
                    all_matches.extend(block_matches)
                    
                    if (i + 1) % 100 == 0 or (i + 1) == len(block_args):
                        logger.info(f"Processed {i+1}/{len(block_args)} blocks, found {len(all_matches)} matches so far")
                except Exception as e:
                    logger.error(f"Error processing block {i}: {e}")
        
        # Deduplicate pairs if multi-pass
        if self.use_multipass and len(all_matches) > 0:
             all_matches = self._deduplicate_pairs(all_matches)

        # Convert dictionaries back to MatchResult objects
        result_objects = [
            MatchResult(
                record_a_idx=m['record_a_idx'],
                record_b_idx=m['record_b_idx'],
                confidence_score=m['confidence_score'],
                match_type=m['match_type'],
                details=m['details']
            )
            for m in all_matches
        ]
        
        elapsed = time.time() - start_time
        logger.info(f"Analysis complete: Found {len(result_objects)} matches in {elapsed:.2f}s")
        logger.info(f"Processing rate: {len(df)/elapsed:.0f} records/second")
        
        return result_objects
    
    def export_results(self, matches: List[MatchResult], df: pd.DataFrame, filename: str = "duplicates.csv"):
        """Export results efficiently"""
        if not matches:
            logger.warning("No matches to export")
            return
        
        logger.info(f"Exporting {len(matches)} matches...")
        
        # Build export data efficiently
        export_rows = []
        
        for match in matches:
            record_a = df.iloc[match.record_a_idx]
            record_b = df.iloc[match.record_b_idx]
            
            crefo_a = str(record_a.get('Crefo', '')).strip()
            crefo_b = str(record_b.get('Crefo', '')).strip()
            match_id = f"{crefo_a}_{crefo_b}" if crefo_a and crefo_b else f"{match.record_a_idx}_{match.record_b_idx}"
            
            # Base row template
            base_row = {
                'match_id': match_id,
                'confidence': match.confidence_score,
                'match_type': match.match_type
            }
            
            # Record A
            row_a = base_row.copy()
            row_a.update({
                'position': 'A',
                'index': match.record_a_idx,
                'vorname': record_a.get('Vorname', ''),
                'name': record_a.get('Name', ''),
                'name2': record_a.get('Name2', ''),
                'strasse': record_a.get('Strasse', ''),
                'hausnummer': record_a.get('HausNummer', ''),
                'plz': record_a.get('Plz', ''),
                'ort': record_a.get('Ort', ''),
                'crefo': crefo_a,
                'geburtstag': record_a.get('Geburtstag', ''),
                'jahrgang': record_a.get('Jahrgang', ''),
            })
            
            # Record B
            row_b = base_row.copy()
            row_b.update({
                'position': 'B',
                'index': match.record_b_idx,
                'vorname': record_b.get('Vorname', ''),
                'name': record_b.get('Name', ''),
                'name2': record_b.get('Name2', ''),
                'strasse': record_b.get('Strasse', ''),
                'hausnummer': record_b.get('HausNummer', ''),
                'plz': record_b.get('Plz', ''),
                'ort': record_b.get('Ort', ''),
                'crefo': crefo_b,
                'geburtstag': record_b.get('Geburtstag', ''),
                'jahrgang': record_b.get('Jahrgang', ''),
            })
            
            export_rows.append(row_a)
            export_rows.append(row_b)
        
        # Create and export DataFrame
        export_df = pd.DataFrame(export_rows)
        export_df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"Exported to {filename}")

def benchmark_performance(df: pd.DataFrame, sample_sizes: List[int] = None):
    """Benchmark the checker on different dataset sizes"""
    if sample_sizes is None:
        sample_sizes = [1000, 10000, 100000, 500000]
    
    checker = UltraFastDuplicateChecker(fuzzy_threshold=0.7, use_parallel=True)
    
    print("\n=== PERFORMANCE BENCHMARK ===")
    print(f"{'Size':<12} {'Time (s)':<12} {'Records/s':<12} {'Matches':<12}")
    print("-" * 50)
    
    for size in sample_sizes:
        if size > len(df):
            continue
        
        sample_df = df.sample(n=min(size, len(df)), random_state=42)
        
        start = time.time()
        matches = checker.analyze_duplicates(sample_df, confidence_threshold=70.0)
        elapsed = time.time() - start
        
        rate = size / elapsed if elapsed > 0 else 0
        
        print(f"{size:<12,} {elapsed:<12.2f} {rate:<12.0f} {len(matches):<12,}")
    
    # Extrapolate to 7.5M
    if sample_sizes and len(df) >= sample_sizes[-1]:
        largest_size = sample_sizes[-1]
        sample_df = df.sample(n=min(largest_size, len(df)), random_state=42)
        start = time.time()
        matches = checker.analyze_duplicates(sample_df, confidence_threshold=70.0)
        elapsed = time.time() - start
        rate = largest_size / elapsed
        
        estimated_time_7_5m = 7_500_000 / rate
        print(f"\nEstimated time for 7.5M records: {estimated_time_7_5m/60:.1f} minutes ({estimated_time_7_5m:.0f}s)")

# Example usage
if __name__ == "__main__":
    print("=== Ultra-Fast Duplicate Checker ===")
    print("Optimized for 7.5 Million+ records\n")
    
    # This would normally load from your database
    # from data import lade_daten
    # df = lade_daten(limit=None)  # Load all 7.5M records
    
    # For demonstration, create sample data
    print("In production, load your full dataset:")
    print("  from data import lade_daten")
    print("  df = lade_daten(limit=None)")
    print("\nThen run:")
    print("  checker = UltraFastDuplicateChecker(fuzzy_threshold=0.7, use_parallel=True)")
    print("  matches = checker.analyze_duplicates(df, confidence_threshold=70.0)")
    print("  checker.export_results(matches, df, 'duplicates_7_5M.csv')")
