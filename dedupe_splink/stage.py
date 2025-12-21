import os
import pandas as pd
from sqlalchemy.engine import Engine
from .preprocess import preprocess_df

def extract_sql_to_parquet(
    engine: Engine,
    query: str,
    out_dir: str,
    chunksize: int = 200_000
) -> None:
    """
    Reads from SQL in chunks, normalizes, and writes partitioned Parquet.
    """
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    print(f"Starting extraction to {out_dir}...")

    try:
        # Use pandas read_sql with chunksize
        chunk_iterator = pd.read_sql(query, engine, chunksize=chunksize)

        for i, df_chunk in enumerate(chunk_iterator):
            # Normalize
            df_norm = preprocess_df(df_chunk)

            # Determine shard key
            def get_shard(plz):
                if pd.isna(plz) or plz == "":
                    return "no_plz"
                plz_str = str(plz)
                if len(plz_str) >= 2:
                    return plz_str[:2]
                return "no_plz"

            df_norm['shard_key'] = df_norm['plz_norm'].apply(get_shard)

            # Write partitions
            for shard_val, group_df in df_norm.groupby('shard_key'):
                shard_dir = os.path.join(out_dir, f"shard={shard_val}")
                os.makedirs(shard_dir, exist_ok=True)

                filename = f"part_{i}.parquet"
                filepath = os.path.join(shard_dir, filename)

                # We KEEP the shard_key because Splink settings requested it as an additional column to retain
                # "additional_columns_to_retain": ["shard_key"]
                # The error was: Binder Error: Values list "l" does not have a column named "shard_key"
                group_df.to_parquet(filepath, index=False)

            print(f"Processed chunk {i}: {len(df_chunk)} rows")

    except Exception as e:
        print(f"Error extracting data: {e}")
        raise
