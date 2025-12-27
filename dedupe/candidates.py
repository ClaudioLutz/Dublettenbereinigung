from __future__ import annotations

import itertools
from typing import Iterator, Tuple
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process


def iter_exact_pairs(
    idx: np.ndarray, cols: dict[str, object], *, max_group: int = 200
) -> Iterator[Tuple[int, int]]:
    """
    Generate exact match pairs (both normal and swapped)
    This implements Stage 1 of the two-stage architecture
    """
    first = cols["first"].iloc[idx].reset_index(drop=True)
    last = cols["last"].iloc[idx].reset_index(drop=True)
    year = pd.Series(cols["year"][idx])
    name2 = cols["name2"].iloc[idx].reset_index(drop=True)

    # Hash for normal name order
    tmp_normal = pd.DataFrame({"f": first, "l": last, "y": year, "n2": name2})
    h_normal = pd.util.hash_pandas_object(tmp_normal, index=False).to_numpy(dtype=np.uint64, copy=False)

    # Hash for swapped name order (first <-> last)
    tmp_swapped = pd.DataFrame({"f": last, "l": first, "y": year, "n2": name2})
    h_swapped = pd.util.hash_pandas_object(tmp_swapped, index=False).to_numpy(dtype=np.uint64, copy=False)

    # Process normal order matches
    order = np.argsort(h_normal, kind="mergesort")
    h_sorted = h_normal[order]
    idx_sorted = idx[order]

    s = 0
    n = len(idx_sorted)
    while s < n:
        e = s + 1
        while e < n and h_sorted[e] == h_sorted[s]:
            e += 1
        g = e - s
        if g > 1:
            if g <= max_group:
                group_ids = idx_sorted[s:e]
                for a, b in itertools.combinations(group_ids, 2):
                    yield (int(a), int(b))
        s = e
    
    # Process swapped order matches
    # Create mapping from original idx to position for comparison
    seen_pairs = set()  # Track pairs we've already yielded to avoid duplicates
    
    order_swap = np.argsort(h_swapped, kind="mergesort")
    h_sorted_swap = h_swapped[order_swap]
    idx_sorted_swap = idx[order_swap]

    s = 0
    while s < n:
        e = s + 1
        while e < n and h_sorted_swap[e] == h_sorted_swap[s]:
            e += 1
        g = e - s
        if g > 1:
            if g <= max_group:
                group_ids = idx_sorted_swap[s:e]
                for a, b in itertools.combinations(group_ids, 2):
                    # Create canonical pair (smaller index first)
                    pair = (min(int(a), int(b)), max(int(a), int(b)))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        yield pair
        s = e


def iter_fuzzy_pairs(
    idx: np.ndarray, cols: dict[str, object], *, k: int = 10, name_threshold: int = 88
) -> Iterator[Tuple[int, int]]:
    names = cols["full_name"].iloc[idx].tolist()
    pos_to_row = idx

    if len(idx) <= 400:
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if fuzz.WRatio(names[i], names[j]) >= name_threshold:
                    yield (int(pos_to_row[i]), int(pos_to_row[j]))
        return

    for i, q in enumerate(names):
        matches = process.extract(
            q, names, scorer=fuzz.WRatio, score_cutoff=name_threshold, limit=k
        )
        for _, _, j in matches:
            if j <= i:
                continue
            yield (int(pos_to_row[i]), int(pos_to_row[j]))
