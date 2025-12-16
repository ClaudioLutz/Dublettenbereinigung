"""
Duplicate Checker POC for Fraud Detection
==========================================

Implements German business rules for duplicate detection with fuzzy matching capabilities.
Based on brainstorming session from 2025-11-14 and analysis document.

Business Rules (in German):
- Ist ein Zweitname auf beiden Archiven vorhanden muss er identisch sein (Gross-Klein-Schreibung wird ignoriert)
- Ist ein Geburtsdatum auf beiden potentiellen Dubletten vorhanden muss mindestens das Jahr des Geburtsdatums übereinstimmen
- Ist ein Geburtsdatum und auf dem anderen Archiv ein Jahrgang gesetzt, so müssen die beiden Jahreszahlen übereinstimmen
- Sind auf beiden Archiven kein Geburtstag aber jeweils ein Jahrgang gesetzt, so muss dieser übereinstimmen
- Ist auf einem Archiv ein Geburtsdatum und ein Jahrgang gesetzt so wird der Jahrgang ignoriert
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import re
from unidecode import unidecode
from rapidfuzz import fuzz, distance
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MatchResult:
    """Result of a duplicate check between two records"""
    record_a_idx: int
    record_b_idx: int
    confidence_score: float
    match_type: str  # 'exact', 'fuzzy_normal', 'fuzzy_swapped'
    details: Dict[str, any]

class GermanNameNormalizer:
    """Handles German-specific name normalization"""
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize German names: handle umlauts, case, accents"""
        if pd.isna(name) or name is None:
            return ""
        
        name = str(name).strip()
        # Convert to lowercase
        name = name.lower()
        # Custom German replacements first
        name = name.replace('ß', 'ss')
        # Remove accents/diacritics
        name = unidecode(name)
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    @staticmethod
    def normalize_zweitname(zweitname: str) -> str:
        """Normalize Zweitname with case-insensitive comparison"""
        if pd.isna(zweitname) or zweitname is None:
            return ""
        return str(zweitname).strip().lower()

class BusinessRulesEngine:
    """Implements German business rules for duplicate detection"""
    
    @staticmethod
    def check_zweitname_rule(zweitname_a: str, zweitname_b: str) -> bool:
        """
        Ist ein Zweitname auf beiden Archiven vorhanden muss er identisch sein 
        (Gross-Klein-Schreibung wird ignoriert)
        """
        norm_a = GermanNameNormalizer.normalize_zweitname(zweitname_a)
        norm_b = GermanNameNormalizer.normalize_zweitname(zweitname_b)
        
        # If both have Zweitname, they must match (case-insensitive)
        if norm_a and norm_b:
            return norm_a == norm_b
        
        # If one or both are empty, rule passes
        return True
    
    @staticmethod
    def extract_year_from_date(date_str: str) -> Optional[int]:
        """Extract year from date string"""
        if pd.isna(date_str) or date_str is None:
            return None
        
        try:
            # Handle various date formats
            date_str = str(date_str).strip()
            if len(date_str) >= 4:
                # Try to extract 4-digit year
                year_match = re.search(r'(\d{4})', date_str)
                if year_match:
                    return int(year_match.group(1))
        except:
            pass
        
        return None
    
    @staticmethod
    def check_date_rule(geburtstag_a: str, jahrgang_a: str, 
                       geburtstag_b: str, jahrgang_b: str) -> bool:
        """
        Complex date matching rules:
        - Ist ein Geburtsdatum auf beiden potentiellen Dubletten vorhanden muss mindestens das Jahr des Geburtsdatums übereinstimmen
        - Ist ein Geburtsdatum und auf dem anderen Archiv ein Jahrgang gesetzt, so müssen die beiden Jahreszahlen übereinstimmen
        - Sind auf beiden Archiven kein Geburtstag aber jeweils ein Jahrgang gesetzt, so muss dieser übereinstimmen
        - Ist auf einem Archiv ein Geburtsdatum und ein Jahrgang gesetzt so wird der Jahrgang ignoriert
        """
        
        # Extract years from dates
        year_a = BusinessRulesEngine.extract_year_from_date(geburtstag_a)
        year_b = BusinessRulesEngine.extract_year_from_date(geburtstag_b)
        
        # Extract jahrgang as integer
        # FIX: Handle float values (e.g., '1998.0') by converting to float first
        jg_a = None
        jg_b = None
        
        try:
            if jahrgang_a and not pd.isna(jahrgang_a):
                # Convert to float first, then to int to handle '1998.0' format
                jg_a = int(float(str(jahrgang_a).strip()))
        except (ValueError, TypeError):
            jg_a = None
            
        try:
            if jahrgang_b and not pd.isna(jahrgang_b):
                # Convert to float first, then to int to handle '1963.0' format
                jg_b = int(float(str(jahrgang_b).strip()))
        except (ValueError, TypeError):
            jg_b = None
        
        # Rule 4 (Priority Rule): If a record has both geburtstag and jahrgang, ignore jahrgang
        # Use effective years - prioritize birth date year over birth year
        effective_year_a = year_a if year_a else jg_a
        effective_year_b = year_b if year_b else jg_b
        
        # Now compare effective years
        if effective_year_a and effective_year_b:
            # Both have year information - they must match
            return effective_year_a == effective_year_b
        elif effective_year_a is None and effective_year_b is None:
            # Neither has year information - rule passes (no conflict)
            return True
        else:
            # One has year information, the other doesn't - REJECT the match
            # This is an ambiguous case that should not be considered a duplicate
            return False

class FuzzyMatcher:
    """Handles fuzzy matching with name swapping detection"""
    
    @staticmethod
    def name_similarity(name1: str, name2: str) -> float:
        """Calculate similarity between two names using RapidFuzz"""
        norm1 = GermanNameNormalizer.normalize_name(name1)
        norm2 = GermanNameNormalizer.normalize_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Use QRatio for normalized comparison
        return fuzz.QRatio(norm1, norm2) / 100.0
    
    @staticmethod
    def compare_name_combinations(vorname_a: str, name_a: str, 
                                 vorname_b: str, name_b: str,
                                 threshold: float = 0.8) -> Dict[str, float]:
        """
        Compare all 4 combinations of name matching:
        1. Normal: VornameA=VornameB, NameA=NameB
        2. Swapped: VornameA=NameB, NameA=VornameB
        """
        
        # Normal combination
        normal_vorname_sim = FuzzyMatcher.name_similarity(vorname_a, vorname_b)
        normal_name_sim = FuzzyMatcher.name_similarity(name_a, name_b)
        normal_score = (normal_vorname_sim + normal_name_sim) / 2
        
        # Swapped combination
        swapped_vorname_sim = FuzzyMatcher.name_similarity(vorname_a, name_b)
        swapped_name_sim = FuzzyMatcher.name_similarity(name_a, vorname_b)
        swapped_score = (swapped_vorname_sim + swapped_name_sim) / 2
        
        return {
            'normal_score': normal_score,
            'swapped_score': swapped_score,
            'normal_vorname_sim': normal_vorname_sim,
            'normal_name_sim': normal_name_sim,
            'swapped_vorname_sim': swapped_vorname_sim,
            'swapped_name_sim': swapped_name_sim,
            'best_score': max(normal_score, swapped_score),
            'is_swapped': swapped_score > normal_score
        }

class DuplicateChecker:
    """Main duplicate detection engine"""
    
    def __init__(self, fuzzy_threshold: float = 0.8):
        self.fuzzy_threshold = fuzzy_threshold
        self.business_rules = BusinessRulesEngine()
        self.fuzzy_matcher = FuzzyMatcher()
        
    def check_exact_match(self, record_a: pd.Series, record_b: pd.Series) -> Optional[MatchResult]:
        """Check exact match based on business rules"""
        
        # Check Zweitname rule
        if not self.business_rules.check_zweitname_rule(
            record_a.get('Name2'), record_b.get('Name2')):
            return None
        
        # Check date rules
        if not self.business_rules.check_date_rule(
            record_a.get('Geburtstag'), record_a.get('Jahrgang'),
            record_b.get('Geburtstag'), record_b.get('Jahrgang')):
            return None
        
        # Exact matching for other fields
        exact_matches = 0
        total_fields = 0
        
        # Check name fields (exact)
        if not pd.isna(record_a.get('Vorname')) and not pd.isna(record_b.get('Vorname')):
            total_fields += 1
            if str(record_a['Vorname']).strip() == str(record_b['Vorname']).strip():  # Case-sensitive exact match
                exact_matches += 1
        
        if not pd.isna(record_a.get('Name')) and not pd.isna(record_b.get('Name')):
            total_fields += 1
            if str(record_a['Name']).strip() == str(record_b['Name']).strip():  # Case-sensitive exact match
                exact_matches += 1
        
        # Check address fields (exact)
        address_fields = ['Strasse', 'HausNummer', 'Plz', 'Ort']
        for field in address_fields:
            if not pd.isna(record_a.get(field)) and not pd.isna(record_b.get(field)):
                total_fields += 1
                if str(record_a[field]).strip() == str(record_b[field]).strip():
                    exact_matches += 1
        
        if total_fields == 0:
            return None
        
        exact_ratio = exact_matches / total_fields
        
        # High confidence for exact matches - require ALL fields to match exactly
        if exact_ratio >= 0.95:  # 95% of fields match exactly (almost all)
            confidence = 85 + (exact_ratio * 15)  # 85-100 range
            
            return MatchResult(
                record_a_idx=record_a.name if hasattr(record_a, 'name') else -1,
                record_b_idx=record_b.name if hasattr(record_b, 'name') else -1,
                confidence_score=confidence,
                match_type='exact',
                details={
                    'exact_ratio': exact_ratio,
                    'exact_matches': exact_matches,
                    'total_fields': total_fields
                }
            )
        
        return None
    
    def check_fuzzy_match(self, record_a: pd.Series, record_b: pd.Series) -> Optional[MatchResult]:
        """Check fuzzy match with name swapping detection"""
        
        # Check Zweitname rule
        if not self.business_rules.check_zweitname_rule(
            record_a.get('Name2'), record_b.get('Name2')):
            return None
        
        # Check date rules
        if not self.business_rules.check_date_rule(
            record_a.get('Geburtstag'), record_a.get('Jahrgang'),
            record_b.get('Geburtstag'), record_b.get('Jahrgang')):
            return None
        
        # Fuzzy name matching
        name_results = self.fuzzy_matcher.compare_name_combinations(
            record_a.get('Vorname', ''), record_a.get('Name', ''),
            record_b.get('Vorname', ''), record_b.get('Name', ''),
            self.fuzzy_threshold
        )
        
        if name_results['best_score'] < self.fuzzy_threshold:
            return None
        
        # Check address fields (exact for POC)
        address_matches = 0
        total_address_fields = 0
        address_fields = ['Strasse', 'HausNummer', 'Plz', 'Ort']
        
        for field in address_fields:
            if not pd.isna(record_a.get(field)) and not pd.isna(record_b.get(field)):
                total_address_fields += 1
                if str(record_a[field]).strip() == str(record_b[field]).strip():
                    address_matches += 1
        
        address_ratio = address_matches / max(total_address_fields, 1)
        
        # Calculate confidence score
        base_confidence = name_results['best_score'] * 50  # 0-50 from names
        address_bonus = address_ratio * 30  # 0-30 from addresses
        swap_bonus = 10 if name_results['is_swapped'] else 0  # Bonus for catching swaps
        
        confidence = base_confidence + address_bonus + swap_bonus
        confidence = min(confidence, 95)  # Cap at 95 for fuzzy matches
        
        match_type = 'fuzzy_swapped' if name_results['is_swapped'] else 'fuzzy_normal'
        
        return MatchResult(
            record_a_idx=record_a.name if hasattr(record_a, 'name') else -1,
            record_b_idx=record_b.name if hasattr(record_b, 'name') else -1,
            confidence_score=confidence,
            match_type=match_type,
            details={
                'name_results': name_results,
                'address_ratio': address_ratio,
                'address_matches': address_matches,
                'total_address_fields': total_address_fields
            }
        )
    
    def find_duplicates(self, df: pd.DataFrame, confidence_threshold: float = 70.0) -> List[MatchResult]:
        """
        Find duplicates in DataFrame using two-stage approach
        Stage 1: Exact matching
        Stage 2: Fuzzy matching for remaining candidates
        """
        logger.info(f"Starting duplicate detection for {len(df)} records")
        
        # Reset index to ensure we have proper indices
        df = df.reset_index(drop=True)
        matches = []
        
        # Stage 1: Exact matching
        logger.info("Stage 1: Exact matching")
        for i in range(len(df)):
            for j in range(i + 1, len(df)):
                exact_match = self.check_exact_match(df.iloc[i], df.iloc[j])
                if exact_match and exact_match.confidence_score >= confidence_threshold:
                    exact_match.record_a_idx = i
                    exact_match.record_b_idx = j
                    matches.append(exact_match)
        
        logger.info(f"Found {len(matches)} exact matches")
        
        # Stage 2: Fuzzy matching (only for records that didn't match exactly)
        logger.info("Stage 2: Fuzzy matching")
        matched_indices = set()
        for match in matches:
            matched_indices.add(match.record_a_idx)
            matched_indices.add(match.record_b_idx)
        
        fuzzy_matches = []
        for i in range(len(df)):
            if i in matched_indices:
                continue
            for j in range(i + 1, len(df)):
                if j in matched_indices:
                    continue
                
                # Optional: PLZ blocking for performance
                plz_a = str(df.iloc[i].get('Plz', '')).strip()
                plz_b = str(df.iloc[j].get('Plz', '')).strip()
                
                if plz_a and plz_b and plz_a != plz_b:
                    continue  # Skip if different PLZ (performance optimization)
                
                fuzzy_match = self.check_fuzzy_match(df.iloc[i], df.iloc[j])
                if fuzzy_match and fuzzy_match.confidence_score >= confidence_threshold:
                    fuzzy_match.record_a_idx = i
                    fuzzy_match.record_b_idx = j
                    fuzzy_matches.append(fuzzy_match)
        
        logger.info(f"Found {len(fuzzy_matches)} fuzzy matches")
        
        # Combine and sort by confidence
        all_matches = matches + fuzzy_matches
        all_matches.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return all_matches

def create_sample_data() -> pd.DataFrame:
    """Create sample data for testing the duplicate checker"""
    
    sample_data = [
        # Exact duplicates
        {
            'Name': 'Mustermann',
            'Vorname': 'Max',
            'Name2': '',
            'Strasse': 'Musterstrasse',
            'HausNummer': '1',
            'Plz': '12345',
            'Ort': 'Musterstadt',
            'Geburtstag': '1980-01-15',
            'Jahrgang': None,
            'Quelle_95': 'A'
        },
        {
            'Name': 'Mustermann',
            'Vorname': 'Max',
            'Name2': '',
            'Strasse': 'Musterstrasse',
            'HausNummer': '1',
            'Plz': '12345',
            'Ort': 'Musterstadt',
            'Geburtstag': '1980-01-15',
            'Jahrgang': None,
            'Quelle_95': 'B'
        },
        # Fuzzy name match - typo
        {
            'Name': 'Mustermann',
            'Vorname': 'Mux',  # Typo for Max
            'Name2': '',
            'Strasse': 'Musterstrasse',
            'HausNummer': '1',
            'Plz': '12345',
            'Ort': 'Musterstadt',
            'Geburtstag': '1980-01-15',
            'Jahrgang': None,
            'Quelle_95': 'C'
        },
        # Name swapped
        {
            'Name': 'Max',  # Swapped
            'Vorname': 'Mustermann',  # Swapped
            'Name2': '',
            'Strasse': 'Musterstrasse',
            'HausNummer': '1',
            'Plz': '12345',
            'Ort': 'Musterstadt',
            'Geburtstag': '1980-01-15',
            'Jahrgang': None,
            'Quelle_95': 'D'
        },
        # German umlaut variation
        {
            'Name': 'Müller',
            'Vorname': 'Hans',
            'Name2': '',
            'Strasse': 'Müllerstrasse',
            'HausNummer': '2',
            'Plz': '54321',
            'Ort': 'Müllendorf',
            'Geburtstag': '1975-05-20',
            'Jahrgang': None,
            'Quelle_95': 'E'
        },
        {
            'Name': 'Mueller',  # Normalized version
            'Vorname': 'Hans',
            'Name2': '',
            'Strasse': 'Müllerstrasse',
            'HausNummer': '2',
            'Plz': '54321',
            'Ort': 'Müllendorf',
            'Geburtstag': '1975-05-20',
            'Jahrgang': None,
            'Quelle_95': 'F'
        },
        # Date rule test cases
        {
            'Name': 'Schmidt',
            'Vorname': 'Anna',
            'Name2': 'Maria',
            'Strasse': 'Schmidtweg',
            'HausNummer': '3',
            'Plz': '11111',
            'Ort': 'Schmidtstadt',
            'Geburtstag': '1990-12-01',
            'Jahrgang': None,
            'Quelle_95': 'G'
        },
        {
            'Name': 'Schmidt',
            'Vorname': 'Anna',
            'Name2': 'maria',  # Case insensitive match
            'Strasse': 'Schmidtweg',
            'HausNummer': '3',
            'Plz': '11111',
            'Ort': 'Schmidtstadt',
            'Geburtstag': None,
            'Jahrgang': '1990',  # Year matches geburtstag year
            'Quelle_95': 'H'
        },
        # Rule 4 test case: Record with both geburtstag and jahrgang (jahrgang should be ignored)
        {
            'Name': 'Wagner',
            'Vorname': 'Thomas',
            'Name2': '',
            'Strasse': 'Wagnerweg',
            'HausNummer': '4',
            'Plz': '22222',
            'Ort': 'Wagnerstadt',
            'Geburtstag': '1985-06-15',  # Birth date year is 1985
            'Jahrgang': '1980',  # Different year - should be ignored due to Rule 4
            'Quelle_95': 'I'
        },
        {
            'Name': 'Wagner',
            'Vorname': 'Thomas',
            'Name2': '',
            'Strasse': 'Wagnerweg',
            'HausNummer': '4',
            'Plz': '22222',
            'Ort': 'Wagnerstadt',
            'Geburtstag': None,
            'Jahrgang': '1985',  # Should match the birth date year from record I
            'Quelle_95': 'J'
        },
        # Real-world bug test case: Should NOT match but currently does
        {
            'Name': 'Gloor',
            'Vorname': 'David Pablo',
            'Name2': '',
            'Strasse': 'Buckhauserstrasse',
            'HausNummer': '1',
            'Plz': '804800',
            'Ort': 'Zürich',
            'Geburtstag': '',  # Empty
            'Jahrgang': '1998',  # Should be effective year 1998
            'Quelle_95': 'BUG_TEST_A'
        },
        {
            'Name': 'Gloor',
            'Vorname': 'David Pablo',
            'Name2': '',
            'Strasse': 'Buckhauserstrasse',
            'HausNummer': '1',
            'Plz': '804800',
            'Ort': 'Zürich',
            'Geburtstag': '16.07.1963',  # Birth date year 1963
            'Jahrgang': '1963',  # Should be ignored due to Rule 4
            'Quelle_95': 'BUG_TEST_B'
        },
        # Non-matching case
        {
            'Name': 'Different',
            'Vorname': 'Person',
            'Name2': '',
            'Strasse': 'Other Street',
            'HausNummer': '99',
            'Plz': '99999',
            'Ort': 'Other City',
            'Geburtstag': '2000-01-01',
            'Jahrgang': None,
            'Quelle_95': 'K'
        }
    ]
    
    return pd.DataFrame(sample_data)

def main():
    """Main function to test the duplicate checker"""
    
    print("=== Duplicate Checker POC for Fraud Detection ===")
    print("Based on German business rules and fuzzy matching architecture")
    print()
    
    # Create sample data
    df = create_sample_data()
    print(f"Created sample dataset with {len(df)} records")
    print()
    
    # Initialize duplicate checker
    checker = DuplicateChecker(fuzzy_threshold=0.7)
    
    # Find duplicates
    matches = checker.find_duplicates(df, confidence_threshold=60.0)
    
    print(f"Found {len(matches)} potential duplicates:")
    print("=" * 80)
    
    for i, match in enumerate(matches, 1):
        record_a = df.iloc[match.record_a_idx]
        record_b = df.iloc[match.record_b_idx]
        
        print(f"\nMatch {i}: {match.match_type.upper()} (Confidence: {match.confidence_score:.1f}%)")
        print(f"Record A (Index {match.record_a_idx}): {record_a['Vorname']} {record_a['Name']} - {record_a['Plz']} {record_a['Ort']}")
        print(f"Record B (Index {match.record_b_idx}): {record_b['Vorname']} {record_b['Name']} - {record_b['Plz']} {record_b['Ort']}")
        
        if match.match_type == 'fuzzy_normal' or match.match_type == 'fuzzy_swapped':
            name_results = match.details['name_results']
            print(f"  Name similarity (normal): {name_results['normal_score']:.2f}")
            print(f"  Name similarity (swapped): {name_results['swapped_score']:.2f}")
            print(f"  Address matches: {match.details['address_ratio']:.2f}")
    
    print("\n=== Summary ===")
    exact_matches = [m for m in matches if m.match_type == 'exact']
    fuzzy_matches = [m for m in matches if m.match_type.startswith('fuzzy')]
    
    print(f"Exact matches: {len(exact_matches)}")
    print(f"Fuzzy matches: {len(fuzzy_matches)}")
    print(f"Total matches: {len(matches)}")
    
    avg_confidence = np.mean([m.confidence_score for m in matches]) if matches else 0
    print(f"Average confidence: {avg_confidence:.1f}%")

if __name__ == "__main__":
    main()
