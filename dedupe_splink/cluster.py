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
) -> None:
    con = duckdb.connect(database=":memory:")
    df = con.execute(
        f"SELECT {left_col} as l, {right_col} as r FROM read_parquet('{edges_parquet_glob}')"
    ).fetch_df()

    uf = UnionFind()
    for l, r in zip(df["l"].tolist(), df["r"].tolist()):
        uf.union(l, r)

    # Build mapping: id -> root
    all_ids = pd.unique(pd.concat([df["l"], df["r"]], ignore_index=True))
    roots = [uf.find(x) for x in all_ids]
    mapping = pd.DataFrame({"unique_id": all_ids, "cluster_id": roots})

    out_mapping_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(out_mapping_csv, index=False)
