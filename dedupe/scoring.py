from __future__ import annotations

from dataclasses import dataclass
from rapidfuzz import fuzz


@dataclass(frozen=True)
class MatchResult:
    i: int
    j: int
    score: float
    name_score: float
    addr_score: float
    reason: str
    is_swapped: bool = False


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
    Returns dict with normal_score, swapped_score, best_score, is_swapped
    """
    if not first_a or not last_a or not first_b or not last_b:
        return {'best_score': 0.0, 'is_swapped': False, 'normal_score': 0.0, 'swapped_score': 0.0}
    
    # Normal comparison
    normal_first = fuzz.WRatio(first_a, first_b) / 100.0
    normal_last = fuzz.WRatio(last_a, last_b) / 100.0
    normal_score = (normal_first + normal_last) / 2
    
    # Swapped comparison
    swapped_first = fuzz.WRatio(first_a, last_b) / 100.0
    swapped_last = fuzz.WRatio(last_a, first_b) / 100.0
    swapped_score = (swapped_first + swapped_last) / 2
    
    return {
        'normal_score': normal_score,
        'swapped_score': swapped_score,
        'best_score': max(normal_score, swapped_score),
        'is_swapped': swapped_score > normal_score
    }


def score_pair(i: int, j: int, cols: dict[str, object]) -> MatchResult | None:
    """
    Score a pair with business rules:
    1. Date rule (year equality)
    2. Name2/Zweitname rule
    3. Name swapping detection
    4. Two-stage: exact matching, then fuzzy matching
    """
    # Business Rule 1: Date rule
    yi = int(cols["year"][i])
    yj = int(cols["year"][j])
    if yi != -1 and yj != -1 and yi != yj:
        return None

    # Business Rule 2: Zweitname rule
    name2_i = cols["name2"].iloc[i]
    name2_j = cols["name2"].iloc[j]
    last_i = cols["last"].iloc[i]
    last_j = cols["last"].iloc[j]
    
    if not check_zweitname(name2_i, last_i, name2_j, last_j):
        return None

    # Get name components
    first_i = cols["first"].iloc[i]
    first_j = cols["first"].iloc[j]
    
    # Check for exact match (Stage 1)
    is_exact_normal = (first_i == first_j and last_i == last_j and 
                       first_i and last_i and first_j and last_j)
    is_exact_swapped = (first_i == last_j and last_i == first_j and 
                        first_i and last_i and first_j and last_j)
    
    # Get address components
    plz_i = cols["plz"].iloc[i]
    plz_j = cols["plz"].iloc[j]
    house_i = cols["house"].iloc[i]
    house_j = cols["house"].iloc[j]
    street_i = cols["street"].iloc[i]
    street_j = cols["street"].iloc[j]

    plz_score = 100.0 if (plz_i != "" and plz_i == plz_j) else 0.0
    house_score = 100.0 if (house_i != "" and house_i == house_j) else 0.0
    street_score = float(fuzz.WRatio(street_i, street_j)) if street_i and street_j else 0.0

    addr_score = 0.5 * plz_score + 0.25 * house_score + 0.25 * street_score
    
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
    
    address_ratio = address_matches / max(total_address_fields, 1)

    # Stage 1: Exact matches
    if is_exact_normal:
        # Exact normal: 90-100% based on address
        confidence = 90.0 + (address_ratio * 10.0)
        return MatchResult(
            i=i, j=j, 
            score=confidence, 
            name_score=100.0, 
            addr_score=addr_score, 
            reason="exact_normal",
            is_swapped=False
        )
    
    if is_exact_swapped:
        # Exact swapped: 85-95% based on address
        confidence = 85.0 + (address_ratio * 10.0)
        return MatchResult(
            i=i, j=j, 
            score=confidence, 
            name_score=100.0, 
            addr_score=addr_score, 
            reason="exact_swapped",
            is_swapped=True
        )
    
    # Stage 2: Fuzzy matching with swap detection
    name_comparison = compare_names_with_swap(first_i, last_i, first_j, last_j)
    name_score = name_comparison['best_score'] * 100.0
    is_swapped = name_comparison['is_swapped']
    
    # Calculate confidence based on fuzzy match
    # Base: name similarity * 50 (max 50 points from names)
    # Address bonus: address_ratio * 30 (max 30 points from address)
    base_confidence = name_comparison['best_score'] * 50.0
    address_bonus = address_ratio * 30.0
    
    if is_swapped:
        # Fuzzy swapped: apply -5 penalty
        confidence = base_confidence + address_bonus - 5.0
        confidence = min(confidence, 95.0)  # Cap at 95%
        reason = "fuzzy_swapped"
    else:
        # Fuzzy normal
        confidence = base_confidence + address_bonus
        confidence = min(confidence, 95.0)  # Cap at 95%
        reason = "fuzzy_normal"
    
    # PLZ mismatch rule: if different PLZ and score < 95, reject
    if plz_i and plz_j and plz_i != plz_j and confidence < 95:
        return None

    return MatchResult(
        i=i, j=j, 
        score=confidence, 
        name_score=name_score, 
        addr_score=addr_score, 
        reason=reason,
        is_swapped=is_swapped
    )
