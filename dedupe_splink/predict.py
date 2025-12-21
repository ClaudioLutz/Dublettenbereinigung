# dedupe_splink/predict.py
from __future__ import annotations
from pathlib import Path
import duckdb
# Splink 4 imports
from splink import DuckDBAPI, Linker

def predict_shard(
    shard_dir: Path,
    trained_settings_json: Path,
    out_edges_parquet: Path,
    threshold_match_probability: float = 0.95,
    threads: int = 4,
    memory_limit: str = "6GB",
) -> None:
    con = duckdb.connect(database=str(out_edges_parquet.with_suffix(".duckdb")))
    con.execute(f"PRAGMA threads={threads};")
    con.execute(f"PRAGMA memory_limit='{memory_limit}';")

    parquet_glob = str(shard_dir / "*.parquet")
    con.execute(f"CREATE VIEW input_table AS SELECT * FROM read_parquet('{parquet_glob}')")

    settings_str = trained_settings_json.read_text(encoding="utf-8")

    # Splink 4 Linker setup
    db_api = DuckDBAPI(connection=con)
    linker = Linker("input_table", settings_str, db_api)

    # Predict and filter early (critical)
    pred = linker.predict(threshold_match_probability=threshold_match_probability)

    # Persist just the edges we need
    out_edges_parquet.parent.mkdir(parents=True, exist_ok=True)
    pred.to_parquet(str(out_edges_parquet))
