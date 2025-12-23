# dedupe_splink/train.py
from __future__ import annotations
import json
from pathlib import Path
import duckdb

# Splink 4 imports
from splink import DuckDBAPI, Linker
from dedupe_splink.settings import build_splink_settings

def train_model_on_parquet_sample(
    parquet_glob: str,
    out_settings_json: Path,
    unique_id_col: str = "unique_id",
    em_blocking_rule: str | None = None,
    max_u_pairs: int = 2_000_000,
    threads: int = 4,
    memory_limit: str = "6GB",
) -> None:
    settings = build_splink_settings(unique_id_col=unique_id_col)

    if em_blocking_rule is None:
        # A moderately permissive rule for EM training
        em_blocking_rule = "l.plz_prefix3 = r.plz_prefix3 AND l.surname_initial = r.surname_initial"

    con = duckdb.connect(database=":memory:")
    con.execute(f"PRAGMA threads={threads};")
    con.execute(f"PRAGMA memory_limit='{memory_limit}';")

    # Load parquet sample into DuckDB as a view
    con.execute(f"CREATE VIEW input_table AS SELECT * FROM read_parquet('{parquet_glob}')")

    # Splink 4 Linker setup
    db_api = DuckDBAPI(connection=con)
    linker = Linker("input_table", settings, db_api)

    # 1) u probabilities (random pairs)
    linker.training.estimate_u_using_random_sampling(max_pairs=max_u_pairs)

    # 2) m probabilities (EM) - no labels
    linker.training.estimate_parameters_using_expectation_maximisation(
        blocking_rule=em_blocking_rule,
        # speed: disable TF during EM if your version supports it; then enable at predict-time
        # estimate_without_term_frequencies=True,
    )

    trained = linker.misc.save_model_to_json()
    out_settings_json.parent.mkdir(parents=True, exist_ok=True)
    # Handle both dict and string returns
    if isinstance(trained, dict):
        out_settings_json.write_text(json.dumps(trained, indent=2), encoding="utf-8")
    else:
        out_settings_json.write_text(trained, encoding="utf-8")
