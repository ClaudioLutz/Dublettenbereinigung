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
    if cols is None or not params.secondary_split_enabled:
        step = params.max_block_size
        for s in range(0, len(idx), step):
            yield idx[s : s + step]
        return

    street = cols["street"].to_numpy()
    house = cols["house"].to_numpy()
    last = cols["last"].to_numpy()

    # Use pandas for safe slicing (NumPy has no simple char.substr)
    street_s = pd.Series(street[idx], copy=False).astype("string")
    house_s = pd.Series(house[idx], copy=False).astype("string")
    last_s = pd.Series(last[idx], copy=False).astype("string")

    street_prefix4 = street_s.str.slice(0, 4).fillna("").to_numpy()
    last_prefix6 = last_s.str.slice(0, 6).fillna("").to_numpy()

    k2 = np.char.add(np.char.add(street_prefix4, "|"), house_s.fillna("").to_numpy())

    missing = (street_s.to_numpy() == "") | (house_s.to_numpy() == "")
    k2 = k2.astype(object)
    if missing.any():
        k2[missing] = last_prefix6[missing]

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
            step = params.max_block_size
            for s in range(0, len(sub), step):
                yield sub[s : s + step]
        start = end
