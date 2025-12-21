# dedupe_splink/export.py
from __future__ import annotations
from pathlib import Path
import duckdb

def export_edges_csv(edges_parquet: str, staged_parquet: str, out_csv: Path) -> None:
    con = duckdb.connect(database=":memory:")
    con.execute(f"CREATE VIEW edges AS SELECT * FROM read_parquet('{edges_parquet}')")
    con.execute(f"CREATE VIEW records AS SELECT * FROM read_parquet('{staged_parquet}')")

    # This assumes Splink outputs unique_id_l/unique_id_r + match_probability
    df = con.execute("""
      SELECT
        e.unique_id_l, e.unique_id_r,
        e.match_probability,
        l.first_name_norm AS l_first, l.surname_norm AS l_last, l.plz_norm AS l_plz, l.birth_year AS l_year,
        r.first_name_norm AS r_first, r.surname_norm AS r_last, r.plz_norm AS r_plz, r.birth_year AS r_year
      FROM edges e
      JOIN records l ON l.unique_id = e.unique_id_l
      JOIN records r ON r.unique_id = e.unique_id_r
      ORDER BY e.match_probability DESC
    """).fetch_df()

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
