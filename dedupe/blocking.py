from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BlockingParams:
    max_block_size: int = 2000
    small_block_all_pairs: int = 400
    secondary_split_enabled: bool = True


def _last_full(cols: dict[str, object]) -> pd.Series:
    """Helper to combine last + name2 for swap-invariant blocking"""
    last = cols["last"].astype("string")
    name2 = cols.get("name2")
    if name2 is None:
        return last
    name2 = name2.astype("string")
    return (last + " " + name2).str.strip().astype("string")


def compute_primary_key(cols: dict[str, object]) -> pd.Series:
    """Pass A: original order-dependent blocking key"""
    last = cols["last"]
    first = cols["first"]
    plz = cols["plz"]
    year = pd.Series(cols["year"])

    k = (
        last.str.slice(0, 3)
        + "|"
        + first.str.slice(0, 1)
        + "|"
        + plz.str.slice(0, 2)
        + "|"
        + year.astype("string")
    )
    return k.astype("string")


def compute_swap_invariant_key(cols: dict[str, object]) -> pd.Series:
    """
    Pass B: swap-invariant blocking key.
    Idea: build an unordered signature of (first_prefix, last_full_prefix).
    """
    first = cols["first"].astype("string")
    plz = cols["plz"].astype("string")
    year = pd.Series(cols["year"]).astype("string")

    last_full = _last_full(cols)

    a = first.str.slice(0, 3).fillna("").to_numpy(dtype=object)
    b = last_full.str.slice(0, 3).fillna("").to_numpy(dtype=object)

    p_min = np.minimum(a, b)
    p_max = np.maximum(a, b)

    p_min_s = pd.Series(p_min, index=first.index).astype("string")
    p_max_s = pd.Series(p_max, index=first.index).astype("string")

    k = (
        "B|"
        + p_min_s + "|"
        + p_max_s + "|"
        + plz.str.slice(0, 2) + "|"
        + year
    )
    return k.astype("string")


def compute_swap_fallback_for_secondary_split(cols: dict[str, object]) -> pd.Series:
    """
    Used only for split_oversized_block() fallback when street/house is missing.
    Make it swap-invariant too, so swapped duplicates don't get separated in the secondary split.
    """
    first = cols["first"].astype("string")
    last_full = _last_full(cols)

    a = first.str.slice(0, 6).fillna("").to_numpy(dtype=object)
    b = last_full.str.slice(0, 6).fillna("").to_numpy(dtype=object)

    p_min = np.minimum(a, b)
    p_max = np.maximum(a, b)

    # "last" placeholder used by split_oversized_block()
    out = np.char.add(np.char.add(p_min, "|"), p_max)
    return pd.Series(out, index=first.index).astype("string")


def compute_address_building_key(cols: dict[str, object]) -> pd.Series:
    """
    Pass A: address-based blocking at building level.
    Key: PLZ | street_key | house_num
    
    This creates blocks of people at the same building (same address, same house number).
    """
    return cols["addr_key_building"].astype("string")


def compute_address_typo_key(cols: dict[str, object]) -> pd.Series:
    """
    Pass B: typo recovery blocking.
    Key: PLZ | house_num | street_sig
    
    This recovers cases where street name has minor typos/variants.
    street_sig is robust to small differences (first 4 chars, sorted).
    """
    return cols["addr_key_typo"].astype("string")


def iter_blocks(
    primary_key: pd.Series, *, params: BlockingParams, cols: Optional[dict[str, object]] = None
) -> Iterator[np.ndarray]:
    codes, _ = pd.factorize(primary_key, sort=False)
    order = np.argsort(codes, kind="mergesort")
    codes_sorted = codes[order]

    start = 0
    n = len(order)
    while start < n:
        code = codes_sorted[start]
        end = start + 1
        while end < n and codes_sorted[end] == code:
            end += 1

        idx = order[start:end]
        if len(idx) <= params.max_block_size:
            yield idx
        else:
            yield from split_oversized_block(idx, params=params, cols=cols)

        start = end


def split_oversized_block(
    idx: np.ndarray, *, params: BlockingParams, cols: Optional[dict[str, object]] = None
) -> Iterator[np.ndarray]:
    """
    Split oversized address blocks using name-based sub-splitting.
    
    Strategy for address-based blocking:
    - Address is constant within the block (same building)
    - Split by name prefixes to keep similar names together
    - Use deterministic hash bucketing as fallback
    """
    if cols is None or not params.secondary_split_enabled:
        step = params.max_block_size
        for s in range(0, len(idx), step):
            yield idx[s : s + step]
        return

    # Extract name fields for sub-splitting
    last = cols["last"].to_numpy()
    first = cols["first"].to_numpy()

    # Use pandas for safe slicing
    last_s = pd.Series(last[idx], copy=False).astype("string")
    first_s = pd.Series(first[idx], copy=False).astype("string")

    # Primary split: last name prefix (2-3 chars)
    last_prefix2 = last_s.str.slice(0, 2).fillna("").to_numpy()
    last_prefix3 = last_s.str.slice(0, 3).fillna("").to_numpy()
    
    # Secondary split: first name prefix (1-2 chars)
    first_prefix1 = first_s.str.slice(0, 1).fillna("").to_numpy()
    first_prefix2 = first_s.str.slice(0, 2).fillna("").to_numpy()
    
    # Build split key: last_prefix3 | first_prefix1
    k2 = np.char.add(np.char.add(last_prefix3, "|"), first_prefix1)
    
    # For empty names, use hash bucket
    empty_mask = (last_s.to_numpy() == "") | (first_s.to_numpy() == "")
    if empty_mask.any():
        # Use stable hash bucket for empty names
        hash_bucket = pd.Series(idx).mod(10).astype(str).to_numpy()
        k2 = k2.astype(object)
        k2[empty_mask] = hash_bucket[empty_mask]

    codes, _ = pd.factorize(pd.Series(k2), sort=False)
    secondary_order = np.argsort(codes, kind="mergesort")
    order2 = idx[secondary_order]
    codes_sorted = codes[secondary_order]

    start = 0
    n = len(order2)
    while start < n:
        code = codes_sorted[start]
        end = start + 1
        while end < n and codes_sorted[end] == code:
            end += 1

        sub = order2[start:end]
        if len(sub) <= params.max_block_size:
            yield sub
        else:
            # Still too large, try finer split with last_prefix2 | first_prefix2
            yield from _split_by_finer_name_prefix(sub, cols, params.max_block_size)
        start = end


def _split_by_finer_name_prefix(
    idx: np.ndarray, cols: dict[str, object], max_size: int
) -> Iterator[np.ndarray]:
    """
    Finer-grained split using shorter name prefixes.
    Used when initial split still produces oversized blocks.
    """
    last = cols["last"].to_numpy()
    first = cols["first"].to_numpy()
    
    last_s = pd.Series(last[idx], copy=False).astype("string")
    first_s = pd.Series(first[idx], copy=False).astype("string")
    
    # Finer split: last_prefix2 | first_prefix2
    last_prefix2 = last_s.str.slice(0, 2).fillna("").to_numpy()
    first_prefix2 = first_s.str.slice(0, 2).fillna("").to_numpy()
    
    k3 = np.char.add(np.char.add(last_prefix2, "|"), first_prefix2)
    
    codes, _ = pd.factorize(pd.Series(k3), sort=False)
    order3 = np.argsort(codes, kind="mergesort")
    order_final = idx[order3]
    codes_sorted = codes[order3]
    
    start = 0
    n = len(order_final)
    while start < n:
        code = codes_sorted[start]
        end = start + 1
        while end < n and codes_sorted[end] == code:
            end += 1
        
        sub = order_final[start:end]
        if len(sub) <= max_size:
            yield sub
        else:
            # Last resort: chunk deterministically
            for s in range(0, len(sub), max_size):
                yield sub[s : s + max_size]
        start = end
