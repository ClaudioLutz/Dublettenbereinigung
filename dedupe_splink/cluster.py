# dedupe_splink/cluster.py
from __future__ import annotations
from pathlib import Path
import duckdb
import pandas as pd

class UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, x):
        p = self.parent.get(x, x)
        if p != x:
            p = self.find(p)
            self.parent[x] = p
        else:
            self.parent.setdefault(x, x)
        return p

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        rka = self.rank.get(ra, 0)
        rkb = self.rank.get(rb, 0)
        if rka < rkb:
            self.parent[ra] = rb
        elif rka > rkb:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] = rka + 1

def cluster_edges_to_mapping(
    edges_parquet_glob: str,
    out_mapping_csv: Path,
    left_col: str = "unique_id_l",
    right_col: str = "unique_id_r",
    batch_size: int = 250_000,
) -> None:
    con = duckdb.connect(database=":memory:")
    # Create an iterator over the edges instead of fetching all at once
    cur = con.execute(
        f"SELECT {left_col} as l, {right_col} as r FROM read_parquet('{edges_parquet_glob}')"
    )

    uf = UnionFind()
    seen = set()

    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        for l, r in rows:
            # UnionFind needs to track all nodes.
            # We add them to 'seen' to reconstruct the full list of IDs later
            # (or iterate over parent dict keys).
            # The UF implementation auto-adds new nodes on find/union.
            uf.union(l, r)
            seen.add(l)
            seen.add(r)

    # Build mapping: id -> root
    # We can iterate over all nodes seen.
    # Note: UF parent dict contains all nodes involved in unions.
    # But singletons (nodes with no edges) won't be here unless we scan the nodes separately.
    # Assuming this function only clusters linked nodes (which is typical for edge outputs).

    # If we need to include ALL nodes from input, we'd need another input source.
    # But usually cluster mapping is for the connected components found.

    mapping_data = []
    for node in seen:
        root = uf.find(node)
        mapping_data.append({"unique_id": node, "cluster_id": root})

    mapping = pd.DataFrame(mapping_data)

    out_mapping_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(out_mapping_csv, index=False)
