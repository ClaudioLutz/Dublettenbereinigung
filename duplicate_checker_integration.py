"""
Duplicate Checker Integration with data.py - OPTIMIZED VERSION
==============================================================

Integration script that combines the duplicate checker POC with the existing data.py
SQL Server connection to analyze real data from vAdresse_Quelle95.

PERFORMANCE OPTIMIZATIONS:
- Multi-level blocking: PLZ + Street
- Parallel processing of blocks
- Vectorized operations
- Early filtering strategies

Usage:
    python duplicate_checker_integration.py
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging
from collections import defaultdict
import re
from unidecode import unidecode
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import time
from duplicate_checker_poc import DuplicateChecker, MatchResult
from data import lade_daten, engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GermanAddressNormalizer:
    """Handles German address normalization for blocking"""
    
    @staticmethod
    def normalize_street(street: str) -> str:
        """Normalize German street names for blocking"""
        if pd.isna(street) or street is None:
            return ""
        
        street = str(street).strip().lower()
        
        # Handle common German street suffix variations
        suffix_mappings = {
            'str.': 'strasse', 'straße': 'strasse', 'str': 'strasse',
            'weg': 'weg', 'allee': 'allee', 'platz': 'platz',
            'gasse': 'gasse', 'ring': 'ring'
        }
        
        # Replace suffixes
        for old_suffix, new_suffix in suffix_mappings.items():
            if street.endswith(old_suffix):
                street = street[:-len(old_suffix)] + new_suffix
                break
        
        # Remove house numbers (common patterns)
        street = re.sub(r'\s+\d+[a-z]*$', '', street)  # Number at end
        street = re.sub(r'^\d+[a-z]*\s+', '', street)  # Number at start
        
        # Handle umlauts
        street = street.replace('ß', 'ss')
        street = unidecode(street)
        
        # Remove extra whitespace and special chars
        street = re.sub(r'\s+', ' ', street)
        street = re.sub(r'[^a-z\s]', '', street)
        
        return street.strip()
    
    @staticmethod
    def normalize_plz(plz: str) -> str:
        """Normalize German postal codes"""
        if pd.isna(plz) or plz is None:
            return ""
        
        plz = str(plz).strip()
        # Remove non-digit characters
        plz = re.sub(r'\D', '', plz)
        # Pad to 5 digits for German PLZ
        return plz.zfill(5)[:5]

class BlockingStrategy:
    """Implements multi-level blocking for performance optimization"""
    
    def __init__(self):
        self.address_normalizer = GermanAddressNormalizer()
    
    def create_blocking_keys(self, df: pd.DataFrame) -> pd.Series:
        """Create blocking keys for each record"""
        blocking_keys = []
        
        for _, record in df.iterrows():
            # Multi-level blocking: PLZ + Street
            plz = self.address_normalizer.normalize_plz(record.get('Plz', ''))
            street = self.address_normalizer.normalize_street(record.get('Strasse', ''))
            
            if plz and street:
                blocking_key = f"{plz}_{street}"
            elif plz:
                # Fallback to PLZ-only if street missing
                blocking_key = f"plz_only_{plz}"
            elif street:
                # Fallback to street-only if PLZ missing
                blocking_key = f"street_only_{street}"
            else:
                # No address information - special category
                blocking_key = "no_address"
            
            blocking_keys.append(blocking_key)
        
        return pd.Series(blocking_keys, index=df.index)
    
    def create_blocks(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Group records into blocks for efficient comparison"""
        logger.info("Creating address blocks for optimized comparison...")
        start_time = time.time()
        
        blocking_keys = self.create_blocking_keys(df)
        df_with_keys = df.copy()
        df_with_keys['blocking_key'] = blocking_keys
        
        # Group by blocking key, preserving original indices
        blocks = defaultdict(list)
        for idx, row in df_with_keys.iterrows():
            blocks[row['blocking_key']].append((idx, row))
        
        # Convert to DataFrames with preserved indices
        block_dfs = {}
        for key, records in blocks.items():
            if len(records) > 1:  # Only keep blocks with multiple records
                # Extract original indices and data separately
                original_indices = [record[0] for record in records]
                block_data = [record[1] for record in records]
                block_df = pd.DataFrame(block_data).reset_index(drop=True)
                block_dfs[key] = (block_df, original_indices)
        
        # Log statistics
        total_records = sum(len(block_df) for block_df in block_dfs.values())
        avg_block_size = total_records / len(block_dfs) if block_dfs else 0
        elapsed_time = time.time() - start_time
        
        logger.info(f"Created {len(block_dfs)} blocks from {len(df)} records in {elapsed_time:.2f}s")
        logger.info(f"Average block size: {avg_block_size:.1f} records")
        logger.info(f"Total records in blocks: {total_records}")
        
        # Calculate potential comparison reduction
        original_comparisons = len(df) * (len(df) - 1) // 2
        blocked_comparisons = sum(len(block) * (len(block) - 1) // 2 for block in block_dfs.values())
        reduction_pct = (1 - blocked_comparisons / original_comparisons) * 100 if original_comparisons > 0 else 0
        
        logger.info(f"Comparison reduction: {original_comparisons:,} -> {blocked_comparisons:,} ({reduction_pct:.1f}% reduction)")
        
        return block_dfs

class OptimizedDuplicateChecker:
    """Optimized duplicate checker with blocking and parallel processing"""
    
    def __init__(self, fuzzy_threshold: float = 0.8):
        self.duplicate_checker = DuplicateChecker(fuzzy_threshold=fuzzy_threshold)
        self.blocking_strategy = BlockingStrategy()
        
    def find_duplicates_in_block(self, block_df: pd.DataFrame, confidence_threshold: float, 
                                original_indices: List[int]) -> List[MatchResult]:
        """Find duplicates within a single block"""
        if len(block_df) < 2:
            return []
        
        matches = []
        
        # Use the original duplicate checker logic but only within the block
        for i in range(len(block_df)):
            for j in range(i + 1, len(block_df)):
                record_i = block_df.iloc[i]
                record_j = block_df.iloc[j]
                
                # DEBUG: Print details for problematic case
                is_gloor_case = (('Gloor' in str(record_i.get('Name', '')) and 'David Pablo' in str(record_i.get('Vorname', ''))) or
                                 ('Gloor' in str(record_j.get('Name', '')) and 'David Pablo' in str(record_j.get('Vorname', ''))))
                
                if is_gloor_case:
                    print(f"DEBUG: Checking potential Gloor case:")
                    print(f"  Record {i}: {record_i.get('Vorname')} {record_i.get('Name')}")
                    print(f"    Geburtstag: '{record_i.get('Geburtstag')}', Jahrgang: '{record_i.get('Jahrgang')}'")
                    print(f"  Record {j}: {record_j.get('Vorname')} {record_j.get('Name')}")
                    print(f"    Geburtstag: '{record_j.get('Geburtstag')}', Jahrgang: '{record_j.get('Jahrgang')}'")
                
                # Check exact match first
                exact_match = self.duplicate_checker.check_exact_match(record_i, record_j)
                if exact_match and exact_match.confidence_score >= confidence_threshold:
                    # DEBUG: Print if exact match found for Gloor case
                    if is_gloor_case:
                        print(f"DEBUG: EXACT MATCH FOUND for Gloor case!")
                        print(f"  Confidence: {exact_match.confidence_score}")
                        print(f"  Match Type: {exact_match.match_type}")
                    
                    exact_match.record_a_idx = original_indices[i]
                    exact_match.record_b_idx = original_indices[j]
                    matches.append(exact_match)
                    continue  # Skip fuzzy if exact match found
                
                # Check fuzzy match
                fuzzy_match = self.duplicate_checker.check_fuzzy_match(record_i, record_j)
                if fuzzy_match and fuzzy_match.confidence_score >= confidence_threshold:
                    fuzzy_match.record_a_idx = original_indices[i]
                    fuzzy_match.record_b_idx = original_indices[j]
                    matches.append(fuzzy_match)
        
        return matches
    
    def find_duplicates(self, df: pd.DataFrame, confidence_threshold: float = 70.0, 
                       use_parallel: bool = True) -> List[MatchResult]:
        """
        Find duplicates using optimized blocking strategy
        
        Args:
            df: DataFrame with address data
            confidence_threshold: Minimum confidence score for matches
            use_parallel: Whether to use parallel processing
            
        Returns:
            List of match results
        """
        logger.info(f"Starting optimized duplicate analysis for {len(df)} records")
        start_time = time.time()
        
        # Create blocks
        blocks = self.blocking_strategy.create_blocks(df)
        
        if not blocks:
            logger.warning("No blocks created - no duplicates possible")
            return []
        
        all_matches = []
        
        if use_parallel and len(blocks) > 1:
            # Parallel processing of blocks
            logger.info(f"Processing {len(blocks)} blocks in parallel...")
            num_workers = min(mp.cpu_count(), len(blocks))
            
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                # Submit tasks for each block
                future_to_block = {}
                
                for block_key, block_tuple in blocks.items():
                    block_df, original_indices = block_tuple
                    
                    future = executor.submit(
                        self.find_duplicates_in_block, 
                        block_df, 
                        confidence_threshold,
                        original_indices
                    )
                    future_to_block[future] = block_key
                
                # Collect results
                for future in as_completed(future_to_block):
                    block_key = future_to_block[future]
                    try:
                        block_matches = future.result()
                        all_matches.extend(block_matches)
                        logger.info(f"Block {block_key}: {len(block_matches)} matches")
                    except Exception as e:
                        logger.error(f"Error processing block {block_key}: {e}")
        else:
            # Sequential processing
            logger.info(f"Processing {len(blocks)} blocks sequentially...")
            for block_key, block_tuple in blocks.items():
                block_df, original_indices = block_tuple
                block_matches = self.find_duplicates_in_block(block_df, confidence_threshold, original_indices)
                all_matches.extend(block_matches)
                logger.info(f"Block {block_key}: {len(block_matches)} matches")
        
        # Sort by confidence
        all_matches.sort(key=lambda x: x.confidence_score, reverse=True)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Found {len(all_matches)} potential duplicates in {elapsed_time:.2f}s")
        
        return all_matches

class DuplicateCheckerIntegration:
    """Integration layer between duplicate checker and data.py"""
    
    def __init__(self, fuzzy_threshold: float = 0.8, use_parallel: bool = True):
        self.optimized_checker = OptimizedDuplicateChecker(fuzzy_threshold=fuzzy_threshold)
        self.use_parallel = use_parallel
        
    def load_data_from_sql(self, limit: int = 1000) -> pd.DataFrame:
        """
        Load data from SQL Server using existing data.py functions
        
        Args:
            limit: Maximum number of records to load (for testing)
            
        Returns:
            DataFrame with address data
        """
        query = f"""
        SELECT [Name]
              ,[Vorname]
              ,[Name2]
              ,[Strasse]
              ,[HausNummer]
              ,[Plz]
              ,[Ort]
              ,[Crefo]
              ,[Geburtstag]
              ,[Jahrgang]
              ,[Erfasst]
              ,[Quelle_95]
          FROM [CAG_Analyse].[dbo].[vAdresse_Quelle95]
          Where Erfasst < dateadd(day,-7,getdate())
          ORDER BY [Erfasst] DESC
        """
        
        try:
            logger.info(f"Loading {limit} records from SQL Server...")
            df = lade_daten(engine, query)
            logger.info(f"Successfully loaded {len(df)} records")
            return df
        except Exception as e:
            logger.error(f"Error loading data from SQL Server: {e}")
            raise
    
    def analyze_duplicates(self, df: pd.DataFrame, confidence_threshold: float = 70.0) -> List[MatchResult]:
        """
        Analyze duplicates in the loaded data using optimized approach
        
        Args:
            df: DataFrame with address data
            confidence_threshold: Minimum confidence score for matches
            
        Returns:
            List of match results
        """
        logger.info(f"Starting optimized duplicate analysis for {len(df)} records")
        
        # Basic data cleaning
        df_clean = self._clean_data(df)
        
        # Find duplicates using optimized approach
        matches = self.optimized_checker.find_duplicates(
            df_clean, 
            confidence_threshold, 
            use_parallel=self.use_parallel
        )
        
        logger.info(f"Found {len(matches)} potential duplicates")
        return matches
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Basic data cleaning before duplicate detection"""
        
        # Make a copy to avoid modifying original
        df_clean = df.copy()
        
        # Convert all string columns to string type and strip whitespace
        string_columns = ['Name', 'Vorname', 'Name2', 'Strasse', 'HausNummer', 'Plz', 'Ort']
        
        for col in string_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str).str.strip()
                # Replace 'nan' strings with actual NaN
                df_clean[col] = df_clean[col].replace('nan', pd.NA)
        
        # IMPORTANT: Do NOT clean Geburtstag and Jahrgang - they need original values for date rules
        # Only convert None/NaN to empty string for consistency
        if 'Geburtstag' in df_clean.columns:
            df_clean['Geburtstag'] = df_clean['Geburtstag'].fillna('')
        if 'Jahrgang' in df_clean.columns:
            df_clean['Jahrgang'] = df_clean['Jahrgang'].fillna('')
        
        logger.info(f"Data cleaning completed. {len(df_clean)} records ready for analysis.")
        return df_clean
    
    def generate_report(self, matches: List[MatchResult], df: pd.DataFrame) -> Dict:
        """
        Generate a comprehensive report of duplicate analysis
        
        Args:
            matches: List of match results
            df: Original DataFrame
            
        Returns:
            Dictionary with analysis results
        """
        if not matches:
            return {
                'total_matches': 0,
                'exact_matches': 0,
                'fuzzy_matches': 0,
                'swapped_matches': 0,
                'avg_confidence': 0.0,
                'high_confidence_matches': 0,
                'matches_by_confidence': {},
                'top_matches': []
            }
        
        # Categorize matches
        exact_matches = [m for m in matches if m.match_type == 'exact']
        fuzzy_matches = [m for m in matches if m.match_type.startswith('fuzzy')]
        swapped_matches = [m for m in matches if m.match_type == 'fuzzy_swapped']
        
        # Calculate statistics
        confidences = [m.confidence_score for m in matches]
        avg_confidence = np.mean(confidences)
        high_confidence_matches = len([c for c in confidences if c >= 80.0])
        
        # Confidence distribution
        confidence_ranges = {
            '70-79%': len([c for c in confidences if 70 <= c < 80]),
            '80-89%': len([c for c in confidences if 80 <= c < 90]),
            '90-95%': len([c for c in confidences if 90 <= c < 95]),
            '95-100%': len([c for c in confidences if c >= 95])
        }
        
        # Top matches (highest confidence)
        top_matches = sorted(matches, key=lambda x: x.confidence_score, reverse=True)[:10]
        
        return {
            'total_matches': len(matches),
            'exact_matches': len(exact_matches),
            'fuzzy_matches': len(fuzzy_matches),
            'swapped_matches': len(swapped_matches),
            'avg_confidence': avg_confidence,
            'high_confidence_matches': high_confidence_matches,
            'matches_by_confidence': confidence_ranges,
            'top_matches': top_matches
        }
    
    def print_detailed_results(self, matches: List[MatchResult], df: pd.DataFrame, 
                             max_results: int = 20):
        """
        Print detailed results of duplicate analysis
        
        Args:
            matches: List of match results
            df: Original DataFrame
            max_results: Maximum number of results to display
        """
        print("\n" + "="*100)
        print("DETAILED DUPLICATE ANALYSIS RESULTS")
        print("="*100)
        
        if not matches:
            print("No duplicates found.")
            return
        
        # Sort by confidence (highest first)
        sorted_matches = sorted(matches, key=lambda x: x.confidence_score, reverse=True)
        
        for i, match in enumerate(sorted_matches[:max_results], 1):
            record_a = df.iloc[match.record_a_idx]
            record_b = df.iloc[match.record_b_idx]
            
            print(f"\n{'-'*80}")
            print(f"Match {i}: {match.match_type.upper().replace('_', ' ')}")
            print(f"Confidence: {match.confidence_score:.1f}%")
            print(f"{'-'*80}")
            
            # Record A details
            print(f"\nRECORD A (Index: {match.record_a_idx}):")
            print(f"  Name: {record_a.get('Vorname', 'N/A')} {record_a.get('Name', 'N/A')}")
            print(f"  Zweitname: {record_a.get('Name2', 'N/A')}")
            print(f"  Address: {record_a.get('Strasse', 'N/A')} {record_a.get('HausNummer', 'N/A')}")
            print(f"  Location: {record_a.get('Plz', 'N/A')} {record_a.get('Ort', 'N/A')}")
            print(f"  Birth: {record_a.get('Geburtstag', 'N/A')} (Jahrgang: {record_a.get('Jahrgang', 'N/A')})")
            print(f"  Crefo: {record_a.get('Crefo', 'N/A')}")
            print(f"  Source: {record_a.get('Quelle_95', 'N/A')}")
            
            # Record B details
            print(f"\nRECORD B (Index: {match.record_b_idx}):")
            print(f"  Name: {record_b.get('Vorname', 'N/A')} {record_b.get('Name', 'N/A')}")
            print(f"  Zweitname: {record_b.get('Name2', 'N/A')}")
            print(f"  Address: {record_b.get('Strasse', 'N/A')} {record_b.get('HausNummer', 'N/A')}")
            print(f"  Location: {record_b.get('Plz', 'N/A')} {record_b.get('Ort', 'N/A')}")
            print(f"  Birth: {record_b.get('Geburtstag', 'N/A')} (Jahrgang: {record_b.get('Jahrgang', 'N/A')})")
            print(f"  Crefo: {record_b.get('Crefo', 'N/A')}")
            print(f"  Source: {record_b.get('Quelle_95', 'N/A')}")
            
            # Match details for fuzzy matches
            if match.match_type.startswith('fuzzy'):
                name_results = match.details.get('name_results', {})
                print(f"\nMATCH DETAILS:")
                print(f"  Name similarity (normal): {name_results.get('normal_score', 0):.2f}")
                print(f"  Name similarity (swapped): {name_results.get('swapped_score', 0):.2f}")
                print(f"  Address match ratio: {match.details.get('address_ratio', 0):.2f}")
                print(f"  Names swapped: {'Yes' if name_results.get('is_swapped', False) else 'No'}")
    
    def export_results_to_csv(self, matches: List[MatchResult], df: pd.DataFrame, 
                              filename: str = "duplicate_analysis_results.csv"):
        """
        Export duplicate analysis results to CSV file
        
        Args:
            matches: List of match results
            df: Original DataFrame
            filename: Output filename
        """
        if not matches:
            logger.warning("No matches to export")
            return
        
        # Prepare data for export
        export_data = []
        
        for match in matches:
            record_a = df.iloc[match.record_a_idx]
            record_b = df.iloc[match.record_b_idx]
            
            # Get Crefo numbers for unique match identification
            crefo_a = str(record_a.get('Crefo', '')).strip()
            crefo_b = str(record_b.get('Crefo', '')).strip()
            match_id = f"{crefo_a}_{crefo_b}" if crefo_a and crefo_b else f"{match.record_a_idx}_{match.record_b_idx}"
            
            # Create two separate rows for each match (A and B records below each other)
            row_a = {
                'crefo1_crefo2': match_id,
                'record_position': 'A',
                'confidence_score': match.confidence_score,
                'match_type': match.match_type,
                'record_index': match.record_a_idx,
                'name': f"{record_a.get('Vorname', '')} {record_a.get('Name', '')}".strip(),
                'vorname': record_a.get('Vorname', ''),
                'name_field': record_a.get('Name', ''),
                'name2': record_a.get('Name2', ''),
                'strasse': record_a.get('Strasse', ''),
                'hausnummer': record_a.get('HausNummer', ''),
                'plz': record_a.get('Plz', ''),
                'ort': record_a.get('Ort', ''),
                'crefo': record_a.get('Crefo', ''),
                'geburtstag': record_a.get('Geburtstag', ''),
                'jahrgang': record_a.get('Jahrgang', ''),
                'erfasst': record_a.get('Erfasst', ''),
                'quelle_95': record_a.get('Quelle_95', ''),
            }
            
            row_b = {
                'crefo1_crefo2': match_id,
                'record_position': 'B',
                'confidence_score': match.confidence_score,
                'match_type': match.match_type,
                'record_index': match.record_b_idx,
                'name': f"{record_b.get('Vorname', '')} {record_b.get('Name', '')}".strip(),
                'vorname': record_b.get('Vorname', ''),
                'name_field': record_b.get('Name', ''),
                'name2': record_b.get('Name2', ''),
                'strasse': record_b.get('Strasse', ''),
                'hausnummer': record_b.get('HausNummer', ''),
                'plz': record_b.get('Plz', ''),
                'ort': record_b.get('Ort', ''),
                'crefo': record_b.get('Crefo', ''),
                'geburtstag': record_b.get('Geburtstag', ''),
                'jahrgang': record_b.get('Jahrgang', ''),
                'erfasst': record_b.get('Erfasst', ''),
                'quelle_95': record_b.get('Quelle_95', ''),
            }
            
            # Add fuzzy match details if available (only to first record to avoid duplication)
            if match.match_type.startswith('fuzzy'):
                name_results = match.details.get('name_results', {})
                fuzzy_info = {
                    'name_similarity_normal': name_results.get('normal_score', 0),
                    'name_similarity_swapped': name_results.get('swapped_score', 0),
                    'is_swapped': name_results.get('is_swapped', False),
                    'address_match_ratio': match.details.get('address_ratio', 0)
                }
                row_a.update(fuzzy_info)
                row_b.update(fuzzy_info)
            
            export_data.append(row_a)
            export_data.append(row_b)
        
        # Create DataFrame and export
        export_df = pd.DataFrame(export_data)
        export_df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"Results exported to {filename} with {len(export_df)} matches")

def main():
    """Main function to run the duplicate analysis integration"""
    
    print("=== OPTIMIZED Duplicate Checker Integration with SQL Server ===")
    print("Analyzing vAdresse_Quelle95 for fraud detection duplicates")
    print("Performance Features: PLZ+Street Blocking, Parallel Processing")
    print()
    
    # Initialize integration with optimizations enabled
    # DISABLED parallel processing due to serialization issues with 7M+ records
    integration = DuplicateCheckerIntegration(fuzzy_threshold=0.7, use_parallel=False)
    
    try:
        # Test with larger dataset now that it's optimized
        df = integration.load_data_from_sql(limit=100000)
        print(f"Loaded {len(df)} records from database")
        print()
        
        # Analyze duplicates with optimized approach
        start_time = time.time()
        matches = integration.analyze_duplicates(df, confidence_threshold=70.0)
        elapsed_time = time.time() - start_time
        
        # Generate report
        report = integration.generate_report(matches, df)
        
        # Print summary
        print("=== ANALYSIS SUMMARY ===")
        print(f"Total records analyzed: {len(df)}")
        print(f"Total potential duplicates: {report['total_matches']}")
        print(f"  - Exact matches: {report['exact_matches']}")
        print(f"  - Fuzzy matches: {report['fuzzy_matches']}")
        print(f"  - Swapped name matches: {report['swapped_matches']}")
        print(f"Average confidence: {report['avg_confidence']:.1f}%")
        print(f"High confidence matches (≥80%): {report['high_confidence_matches']}")
        print(f"Processing time: {elapsed_time:.2f} seconds")
        print()
        
        # Print confidence distribution
        print("=== CONFIDENCE DISTRIBUTION ===")
        for range_name, count in report['matches_by_confidence'].items():
            if count > 0:
                print(f"{range_name}: {count} matches")
        print()
        
        # Print detailed results
        integration.print_detailed_results(matches, df, max_results=10)
        
        # Export results
        integration.export_results_to_csv(matches, df, "duplicate_analysis_results_optimized.csv")
        
        print("\n=== ANALYSIS COMPLETE ===")
        print("Results have been exported to 'duplicate_analysis_results_optimized.csv'")
        print(f"Performance improvement: {elapsed_time:.2f}s vs hours for original approach")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        print(f"Analysis failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
