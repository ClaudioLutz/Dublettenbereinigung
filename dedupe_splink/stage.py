# dedupe_splink/stage.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from dedupe.config import DbConfig
from dedupe.io import create_mssql_engine, read_sql_df
from dedupe_splink.preprocess import preprocess_chunk

@dataclass
class StageConfig:
    out_dir: Path
    chunksize: int = 200_000
    unique_id_col: str = "unique_id"   # if missing, we'll create
    plz_col: str = "Plz"

def _write_parquet(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path, compression="zstd")

def stage_query_to_parquet(query: str, db_cfg: DbConfig, cfg: StageConfig) -> None:
    engine = create_mssql_engine(db_cfg)
    reader = read_sql_df(engine, query, chunksize=cfg.chunksize)

    out_base = cfg.out_dir
    out_base.mkdir(parents=True, exist_ok=True)

    offset = 0
    part = 0

    # read_sql_df may return either DF or iterator; normalize:
    if isinstance(reader, pd.DataFrame):
        chunks = [reader]
    else:
        chunks = reader

    for chunk in chunks:
        chunk = chunk.copy()

        # Ensure a unique id exists
        if cfg.unique_id_col not in chunk.columns:
            chunk[cfg.unique_id_col] = range(offset, offset + len(chunk))
        offset += len(chunk)

        # preprocess + add derived fields + shard key
        chunk = preprocess_chunk(chunk, unique_id_col=cfg.unique_id_col)

        # write each shard separately (keeps each run bounded)
        for shard, df_shard in chunk.groupby("shard", sort=False):
            out_path = out_base / f"shard={shard}" / f"part-{part:05d}.parquet"
            _write_parquet(df_shard, out_path)

        part += 1
