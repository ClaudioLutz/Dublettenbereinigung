from __future__ import annotations

from dataclasses import dataclass
from rapidfuzz import fuzz
try:
    import cologne_phonetics
    COLOGNE_PHONETICS_AVAILABLE = True
except ImportError:
    COLOGNE_PHONETICS_AVAILABLE = False


@dataclass(frozen=True)
class MatchResult:
    i: int
    j: int
    score: float
    name_score: float
    addr_score: float
    reason: str
    is_swapped: bool = False


def get_cologne_phonetic(name: str) -> str:
    """
    Get Cologne Phonetic code for a name safely.
    Returns empty string if encoding fails, name is empty, or library not available.
    """
    if not COLOGNE_PHONETICS_AVAILABLE:
        return ''
    
    if not name or not name.strip():
        return ''
    
    try:
        result = cologne_phonetics.encode(str(name).strip())
        if result and len(result) > 0:
            # cologne_phonetics.encode returns list of tuples: [('name', 'code')]
            return result[0][1]
    except:
        pass
    return ''


def check_zweitname(name2_a: str, name_a: str, name2_b: str, name_b: str) -> bool:
    """
    Check Zweitname rule with compound surname support
    
    Handles cases where name2 might be the suffix of name:
    - name="Rohner-Stassek", name2="" 
    - name="Rohner", name2="-Stassek"
    Should match!
    
    Returns True if records pass the Zweitname rule, False otherwise.
    """
    # Already normalized to lowercase and stripped
    norm_name2_a = name2_a.strip() if name2_a else ''
    norm_name_a = name_a.strip() if name_a else ''
    norm_name2_b = name2_b.strip() if name2_b else ''
    norm_name_b = name_b.strip() if name_b else ''
    
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


def compare_names_with_swap(first_a: str, last_a: str, first_b: str, last_b: str) -> dict:
    """
    Compare names with swapping detection
    Returns dict with normal_score, swapped_score, best_score, is_swapped, 
                 first_similarity, last_similarity
    """
    if not first_a or not last_a or not first_b or not last_b:
        return {
            'best_score': 0.0, 
            'is_swapped': False, 
            'normal_score': 0.0, 
            'swapped_score': 0.0,
            'first_similarity': 0.0,
            'last_similarity': 0.0
        }
    
    # Normal comparison
    normal_first = fuzz.WRatio(first_a, first_b) / 100.0
    normal_last = fuzz.WRatio(last_a, last_b) / 100.0
    normal_score = (normal_first + normal_last) / 2
    
    # Swapped comparison
    swapped_first = fuzz.WRatio(first_a, last_b) / 100.0
    swapped_last = fuzz.WRatio(last_a, first_b) / 100.0
    swapped_score = (swapped_first + swapped_last) / 2
    
    # Return individual similarities for gating
    is_swapped = swapped_score > normal_score
    if is_swapped:
        first_similarity = swapped_first
        last_similarity = swapped_last
    else:
        first_similarity = normal_first
        last_similarity = normal_last
    
    return {
        'normal_score': normal_score,
        'swapped_score': swapped_score,
        'best_score': max(normal_score, swapped_score),
        'is_swapped': is_swapped,
        'first_similarity': first_similarity,
        'last_similarity': last_similarity
    }


def get_first_word_bonus(first_a: str, first_b: str, plz_i: str, plz_j: str, 
                         house_num_i: str, house_num_j: str, street_i: str, 
                         street_j: str, ort_i: str, ort_j: str) -> float:
    """
    Calculate bonus for matching first word/token of vorname.
    
    When first word matches exactly, this is strong evidence (e.g., "Joao Manuel" vs "Joao").
    Bonus is higher when other fields also match perfectly.
    
    Args:
        first_a, first_b: First name strings (already normalized)
        plz_i, plz_j, house_num_i, house_num_j, street_i, street_j, ort_i, ort_j: Address fields
        
    Returns:
        Bonus value: 0.10 if everything else matches, 0.05 otherwise, 0.0 if no match
    """
    if not first_a or not first_b:
        return 0.0
    
    # Extract first word/token
    first_word_a = first_a.split()[0] if first_a.split() else ""
    first_word_b = first_b.split()[0] if first_b.split() else ""
    
    if not first_word_a or not first_word_b or first_word_a != first_word_b:
        return 0.0
    
    # First words match! Now check if everything else matches perfectly
    plz_match = (plz_i and plz_j and plz_i == plz_j)
    house_match = (house_num_i and house_num_j and house_num_i == house_num_j)
    
    # Street and ort need fuzzy comparison
    street_score = fuzz.ratio(street_i, street_j) if street_i and street_j else 0.0
    ort_score = fuzz.ratio(ort_i, ort_j) if ort_i and ort_j else 0.0
    
    street_match = street_score >= 95.0
    ort_match = ort_score >= 95.0
    
    # If everything else matches perfectly, give 10% bonus, otherwise 5%
    if plz_match and house_match and street_match and ort_match:
        return 0.10
    else:
        return 0.05


def compute_normalized_address_ratio(plz_i: str, plz_j: str, street_i: str, street_j: str) -> float:
    """
    Compute normalized address ratio for address-assisted matching
    
    Args:
        plz_i, plz_j: PLZ (postal codes) - already normalized
        street_i, street_j: Street names - already normalized
    
    Returns:
        Float between 0.0 and 1.0 representing address match quality
    """
    # PLZ comparison (exact match)
    plz_ratio = 1.0 if plz_i and plz_j and plz_i == plz_j else 0.0
    
    # Street comparison (fuzzy match)
    if street_i and street_j:
        street_ratio = fuzz.ratio(street_i, street_j) / 100.0
    else:
        street_ratio = 0.0
    
    # Weighted combination (PLZ is more discriminative)
    # Require at least one component to be present
    if plz_i or street_i:
        address_ratio = 0.6 * plz_ratio + 0.4 * street_ratio
    else:
        address_ratio = 0.0
    
    return address_ratio


def score_pair(i: int, j: int, cols: dict[str, object], 
               fuzzy_threshold: float = 0.80, 
               enable_address_aware: bool = True) -> MatchResult | None:
    """
    Score a pair with business rules:
    1. DOB/YOB hard gate (exact date mismatch rejection)
    2. Name2/Zweitname rule
    3. Name swapping detection
    4. Two-stage: exact matching, then fuzzy matching
    5. Address-assisted matching (borderline names + strong address)
    6. Phonetic fallback (borderline names + phonetic match)
    7. Stricter threshold when DOB/YOB missing or not exactly matched
    8. STRICT: Require exact DOB AND exact address for fuzzy matches
    
    Args:
        i, j: Indices of records to compare
        cols: Preprocessed columns dictionary
        fuzzy_threshold: Minimum name similarity for fuzzy match (default: 0.80)
        enable_address_aware: Enable address-assisted matching (default: True)
    """
    # Business Rule 1: DOB hard gate (exact date of birth mismatch)
    dob_i = int(cols["dob_ymd"][i])
    dob_j = int(cols["dob_ymd"][j])
    
    # If both have exact DOB and they differ, reject immediately
    if dob_i != -1 and dob_j != -1 and dob_i != dob_j:
        return None
    
    # Year of birth gate (uses Jahrgang or DOB year)
    yob_i = int(cols["yob"][i])
    yob_j = int(cols["yob"][j])
    
    # If both have YOB and they differ, reject
    if yob_i != -1 and yob_j != -1 and yob_i != yob_j:
        return None
    
    # Track DOB/YOB match quality
    both_dob_missing = (dob_i == -1 and dob_j == -1)
    both_yob_missing = (yob_i == -1 and yob_j == -1)
    one_dob_missing = (dob_i == -1 or dob_j == -1) and not both_dob_missing
    both_have_exact_dob = (dob_i != -1 and dob_j != -1 and dob_i == dob_j)
    yob_only_match = (yob_i != -1 and yob_j != -1 and yob_i == yob_j and not both_have_exact_dob)

    # Business Rule 2: Zweitname rule (swap-aware)
    name2_i = cols["name2"].iloc[i]
    name2_j = cols["name2"].iloc[j]
    last_i = cols["last"].iloc[i]
    last_j = cols["last"].iloc[j]
    first_i = cols["first"].iloc[i]
    first_j = cols["first"].iloc[j]
    
    # STRICT: Adjust effective fuzzy threshold based on DOB/address match quality
    # Birth year alone is NOT a strong enough indication - require exact DOB
    effective_fuzzy_threshold = fuzzy_threshold
    
    # Case 1: Both DOB and YOB missing -> require 95% name similarity (very strict)
    if both_dob_missing and both_yob_missing:
        effective_fuzzy_threshold = max(fuzzy_threshold, 0.95)
    
    # Case 2: One DOB missing -> require 90% name similarity (strict)
    # Example: Michaela Asri (has DOB) vs Michaela Rabbani Mughal (no DOB)
    elif one_dob_missing:
        effective_fuzzy_threshold = max(fuzzy_threshold, 0.90)
    
    # Case 3: Both have YOB but no exact DOB -> require 88% name similarity
    # Example: Dominique Tschannen vs Doris Tschannen (both have YOB 1976, no DOB)
    # Birth year alone is insufficient!
    elif yob_only_match:
        effective_fuzzy_threshold = max(fuzzy_threshold, 0.88)
    
    if not check_zweitname(name2_i, last_i, name2_j, last_j):
        # Swapped placement fallback: surname(+name2) might be in Vorname field
        if not check_zweitname(name2_i, last_i, name2_j, first_j) and not check_zweitname(name2_j, last_j, name2_i, first_i):
            return None
    
    # CRITICAL FIX: When name2 is present in one record but not the other,
    # combine name+name2 for fair comparison (swap-aware)
    # Example: "Haller" + "Bensel" vs "Haller Bensel" should match 100%
    last_i_for_comparison = last_i
    last_j_for_comparison = last_j
    
    if name2_i and not name2_j:
        # Combine last_i with name2_i if name2_i is a suffix of last_j OR first_j
        if last_j.endswith(name2_i) or first_j.endswith(name2_i):
            last_i_for_comparison = (last_i + " " + name2_i).strip()
    elif name2_j and not name2_i:
        # Combine last_j with name2_j if name2_j is a suffix of last_i OR first_i
        if last_i.endswith(name2_j) or first_i.endswith(name2_j):
            last_j_for_comparison = (last_j + " " + name2_j).strip()
    
    # Check for exact match (Stage 1) - use the combined names for comparison
    is_exact_normal = (first_i == first_j and last_i_for_comparison == last_j_for_comparison and 
                       first_i and last_i_for_comparison and first_j and last_j_for_comparison)
    is_exact_swapped = (first_i == last_j_for_comparison and last_i_for_comparison == first_j and 
                        first_i and last_i_for_comparison and first_j and last_j_for_comparison)
    
    # Get address components (including parsed house number)
    plz_i = cols["plz"].iloc[i]
    plz_j = cols["plz"].iloc[j]
    house_i = cols["house"].iloc[i]
    house_j = cols["house"].iloc[j]
    house_num_i = cols["house_num"].iloc[i]
    house_num_j = cols["house_num"].iloc[j]
    house_sfx_i = cols["house_sfx"].iloc[i]
    house_sfx_j = cols["house_sfx"].iloc[j]
    street_i = cols["street"].iloc[i]
    street_j = cols["street"].iloc[j]
    ort_i = cols["ort"].iloc[i]
    ort_j = cols["ort"].iloc[j]

    plz_score = 100.0 if (plz_i != "" and plz_i == plz_j) else 0.0
    house_score = 100.0 if (house_i != "" and house_i == house_j) else 0.0
    street_score = float(fuzz.WRatio(street_i, street_j)) if street_i and street_j else 0.0
    ort_score = float(fuzz.WRatio(ort_i, ort_j)) if ort_i and ort_j else 0.0

    addr_score = 0.4 * plz_score + 0.2 * house_score + 0.2 * street_score + 0.2 * ort_score
    
    # Calculate address ratio for confidence
    address_matches = 0
    total_address_fields = 0
    if plz_i and plz_j:
        total_address_fields += 1
        if plz_i == plz_j:
            address_matches += 1
    if house_i and house_j:
        total_address_fields += 1
        if house_i == house_j:
            address_matches += 1
    if street_i and street_j:
        total_address_fields += 1
        if street_score >= 80:  # Consider 80%+ as match
            address_matches += 1
    if ort_i and ort_j:
        total_address_fields += 1
        if ort_score >= 80:  # Consider 80%+ as match
            address_matches += 1
    
    address_ratio = address_matches / max(total_address_fields, 1)

    # Stage 1: Exact matches
    # Names match exactly, but confidence depends on address similarity
    if is_exact_normal or is_exact_swapped:
        # CRITICAL: Different PLZ = very likely different people, reject
        if plz_i and plz_j and plz_i != plz_j:
            # Different PLZ = different people, reject immediately
            return None
        
        # CRITICAL: Require high street similarity (>70%) when both have street data
        # This filters out completely different streets like "Plattenholz" vs "Halden"
        if street_i and street_j and street_score < 70.0:
            # Very different streets = likely different people
            return None
        
        # CRITICAL: Very different house numbers on same street = different people!
        # Use parsed house_num for cleaner comparison
        if house_num_i and house_num_j and house_num_i != house_num_j:
            # Numeric parts differ = different buildings
            return None
        
        # Calculate confidence based on address match quality
        # address_ratio already includes ort_score, street_score, house_score, and plz_score
        # So mismatched cities will naturally reduce the score
        
        if is_exact_normal:
            # Exact normal: Base score depends on address quality
            # Perfect address match: 100%
            # Partial address match: 70-99%
            # Poor address match: 50-70%
            if address_ratio >= 0.9:
                # Very strong address match
                confidence = 95.0 + (address_ratio * 5.0)  # 95-100%
            elif address_ratio >= 0.5:
                # Moderate address match
                confidence = 70.0 + (address_ratio * 25.0)  # 70-95%
            else:
                # Weak address match - names match but addresses very different
                confidence = 50.0 + (address_ratio * 20.0)  # 50-70%
            
            return MatchResult(
                i=i, j=j, 
                score=confidence, 
                name_score=100.0, 
                addr_score=addr_score, 
                reason="exact_normal",
                is_swapped=False
            )
        
        if is_exact_swapped:
            # NEW: Score=100 when everything else matches perfectly
            def _house_equivalent(num1: str, num2: str) -> bool:
                """Check if house numbers are equivalent (same numeric part)"""
                if (not num1) and (not num2):
                    return True
                if num1 and num2:
                    return num1 == num2
                return False
            
            def _strong_text_match(a: str, b: str, score: float) -> bool:
                """Check if text fields match strongly"""
                if (not a) and (not b):
                    return True
                if a and b:
                    return score >= 95.0
                return False
            
            # Check if everything else matches perfectly
            strict_other_match = (
                (plz_i and plz_j and plz_i == plz_j) and
                _house_equivalent(house_num_i, house_num_j) and
                _strong_text_match(street_i, street_j, street_score) and
                _strong_text_match(ort_i, ort_j, ort_score)
            )
            
            if strict_other_match:
                # Perfect match except for swapped names -> Score 100
                confidence = 100.0
            else:
                # Old swapped confidence formula (fallback)
                if address_ratio >= 0.9:
                    confidence = 90.0 + (address_ratio * 5.0)  # 90-95%
                elif address_ratio >= 0.5:
                    confidence = 65.0 + (address_ratio * 25.0)  # 65-90%
                else:
                    confidence = 45.0 + (address_ratio * 20.0)  # 45-65%
            
            return MatchResult(
                i=i, j=j, 
                score=confidence, 
                name_score=100.0, 
                addr_score=addr_score, 
                reason="exact_swapped",
                is_swapped=True
            )
    
    # Stage 2: Fuzzy matching with swap detection - use combined names
    name_comparison = compare_names_with_swap(first_i, last_i_for_comparison, first_j, last_j_for_comparison)
    best_score = name_comparison['best_score']
    is_swapped = name_comparison['is_swapped']
    
    # Check if name similarity meets threshold (use effective threshold)
    if best_score < effective_fuzzy_threshold:
        # NEW: Address-aware gate for borderline name scores (60-threshold range)
        if 0.60 <= best_score < effective_fuzzy_threshold:
            # Check for address-assisted match first (if enabled)
            if enable_address_aware:
                # STRICT: Address-assisted matching also requires exact DOB or both missing
                # Cannot use address-assisted when DOB data quality is poor
                if not both_have_exact_dob and not (both_dob_missing and both_yob_missing):
                    # One DOB missing or YOB-only match -> reject address-assisted path
                    pass  # Fall through to phonetic check or rejection
                else:
                    # NEW: Name similarity gates to prevent family member false positives
                    # Get individual first name and last name similarities
                    first_similarity = name_comparison['first_similarity']
                    last_similarity = name_comparison['last_similarity']
                    
                    # Require minimum first name (75%) and last name (80%) similarity
                    # This rejects: "Hermann" vs "Andreas" (first ~40%), "Meier" vs "Bacher" (last ~20%)
                    if first_similarity < 0.75 or last_similarity < 0.80:
                        # Names too different - reject even with strong address
                        pass  # Fall through to phonetic check
                    else:
                        # Compute normalized address ratio
                        norm_address_ratio = compute_normalized_address_ratio(plz_i, plz_j, street_i, street_j)
                        
                        if norm_address_ratio >= 0.75:
                            # Strong address match + sufficient name similarity -> "address_assisted" match
                            if is_swapped:
                                reason = 'address_assisted_swapped'
                                confidence = 68.0 + (norm_address_ratio * 10.0)  # 68-78%
                            else:
                                reason = 'address_assisted_normal'
                                confidence = 70.0 + (norm_address_ratio * 10.0)  # 70-80%
                            
                            return MatchResult(
                                i=i, j=j,
                                score=confidence,
                                name_score=best_score * 100.0,
                                addr_score=addr_score,
                                reason=reason,
                                is_swapped=is_swapped
                            )
            
            # NEW: Apply first-word matching bonus for borderline cases
            # If first word of vorname matches exactly, this is strong evidence
            first_word_bonus = get_first_word_bonus(
                first_i, first_j, plz_i, plz_j, 
                house_num_i, house_num_j, street_i, street_j, 
                ort_i, ort_j
            )
            
            if first_word_bonus > 0:
                # Boost name score with first-word bonus
                boosted_name_score = min(best_score + first_word_bonus, 1.0)
                
                # Check if boosted score now meets threshold
                if boosted_name_score >= effective_fuzzy_threshold:
                    # Now qualifies as fuzzy match with bonus
                    if is_swapped:
                        reason = 'fuzzy_swapped'
                        confidence = boosted_name_score * 50.0 + address_ratio * 30.0 - 5.0
                        confidence = min(confidence, 95.0)
                    else:
                        reason = 'fuzzy_normal'
                        confidence = boosted_name_score * 50.0 + address_ratio * 30.0
                        confidence = min(confidence, 95.0)
                    
                    return MatchResult(
                        i=i, j=j,
                        score=confidence,
                        name_score=boosted_name_score * 100.0,
                        addr_score=addr_score,
                        reason=reason,
                        is_swapped=is_swapped
                    )
            
            # If address is not strong enough, check phonetic fallback
            if COLOGNE_PHONETICS_AVAILABLE:
                # Get phonetic codes - use combined names for comparison
                v_i_phon = get_cologne_phonetic(first_i)
                n_i_phon = get_cologne_phonetic(last_i_for_comparison)
                v_j_phon = get_cologne_phonetic(first_j)
                n_j_phon = get_cologne_phonetic(last_j_for_comparison)
                
                # Check phonetic match (normal and swapped)
                phonetic_match_normal = (v_i_phon and n_i_phon and v_j_phon and n_j_phon and
                                        v_i_phon == v_j_phon and n_i_phon == n_j_phon)
                phonetic_match_swapped = (v_i_phon and n_i_phon and v_j_phon and n_j_phon and
                                         v_i_phon == n_j_phon and n_i_phon == v_j_phon)
                
                if phonetic_match_normal or phonetic_match_swapped:
                    # Phonetic-assisted match
                    is_swapped = phonetic_match_swapped
                    
                    if is_swapped:
                        reason = 'phonetic_assisted_swapped'
                        confidence = 70.0 + (address_ratio * 10.0)  # 70-80%
                    else:
                        reason = 'phonetic_assisted_normal'
                        confidence = 72.0 + (address_ratio * 10.0)  # 72-82%
                    
                    return MatchResult(
                        i=i, j=j,
                        score=confidence,
                        name_score=best_score * 100.0,
                        addr_score=addr_score,
                        reason=reason,
                        is_swapped=is_swapped
                    )
        
        # No phonetic match and weak address - reject
        return None
    
    # STRICT FUZZY MATCHING RULES
    # For fuzzy matches, require MUCH stricter address matching
    
    # Rule 1: REQUIRE exact address match (PLZ, house number, street) for fuzzy matches
    # when DOB is not an exact match
    if not both_have_exact_dob:
        # No exact DOB match -> addresses must match perfectly
        
        # Require matching PLZ
        if not (plz_i and plz_j and plz_i == plz_j):
            # PLZ missing or different -> reject fuzzy match
            return None
        
        # Require matching house numbers
        if not (house_num_i and house_num_j and house_num_i == house_num_j):
            # House number missing or different -> reject fuzzy match
            return None
        
        # Require very high street similarity (>90%)
        if not (street_i and street_j and street_score >= 90.0):
            # Street missing or too different -> reject fuzzy match
            return None
    
    # Rule 2: Even with exact DOB, require good address similarity
    else:
        # Have exact DOB match -> allow some address flexibility but still strict
        
        # Reject fuzzy matches with poor address similarity
        if address_ratio < 0.50:
            # If addresses are very different, reject unless names are very close (>95%)
            if best_score < 0.95:
                return None
        
        # Strict PLZ mismatch rule
        if plz_i and plz_j and plz_i != plz_j:
            # Different PLZ with fuzzy name match? Reject unless street is very similar (>90%)
            if street_score < 90.0:
                return None
        
        # CRITICAL: Require matching house numbers (if both have house number data)
        if house_num_i and house_num_j and house_num_i != house_num_j:
            # Numeric parts differ = different buildings
            return None
    
    # Calculate confidence score with STRICT penalties for missing DOB
    # Base: name similarity * 50 (max 50 points from names)
    # Address bonus: address_ratio * 30 (max 30 points from address)
    base_confidence = best_score * 50.0
    address_bonus = address_ratio * 30.0
    
    # Apply DOB quality penalties
    dob_penalty = 0.0
    if one_dob_missing:
        # One DOB missing: -15 point penalty
        dob_penalty = 15.0
    elif yob_only_match:
        # YOB-only match (no exact DOB): -10 point penalty
        # Birth year alone is insufficient!
        dob_penalty = 10.0
    elif both_dob_missing and both_yob_missing:
        # Both DOB and YOB missing: -20 point penalty
        dob_penalty = 20.0
    
    if is_swapped:
        # Fuzzy swapped: apply -5 penalty
        confidence = base_confidence + address_bonus - dob_penalty - 5.0
        confidence = max(confidence, 40.0)  # Floor at 40%
        confidence = min(confidence, 85.0)  # Cap at 85% for fuzzy with DOB issues
        reason = "fuzzy_swapped"
    else:
        # Fuzzy normal
        confidence = base_confidence + address_bonus - dob_penalty
        confidence = max(confidence, 40.0)  # Floor at 40%
        confidence = min(confidence, 85.0)  # Cap at 85% for fuzzy with DOB issues
        reason = "fuzzy_normal"

    return MatchResult(
        i=i, j=j, 
        score=confidence, 
        name_score=best_score * 100.0, 
        addr_score=addr_score, 
        reason=reason,
        is_swapped=is_swapped
    )
