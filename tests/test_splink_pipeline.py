import os
import shutil
import pandas as pd
from unittest import TestCase, main
import sys

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dedupe_splink.preprocess import preprocess_df
from dedupe_splink.settings import get_settings

class TestSplinkPipeline(TestCase):
    def setUp(self):
        self.test_dir = "test_output"
        os.makedirs(self.test_dir, exist_ok=True)
        self.parquet_cache = os.path.join(self.test_dir, "cache")
        self.results_dir = os.path.join(self.test_dir, "results")

        # Dummy data
        self.df = pd.DataFrame({
            "Name": ["Müller", "Mueller", "Schmidt"],
            "Vorname": ["Hans", "Hannes", "Peter"],
            "Plz": ["12345", "12345", "54321"],
            "Strasse": ["Hauptstr", "Hauptstrasse", "Nebenweg"],
            "HausNummer": ["1", "1", "2"],
            "Geburtstag": ["1980-01-01", "1980-01-01", "1990-05-05"]
        })

    def tearDown(self):
        # Clean up
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_preprocess(self):
        df_norm = preprocess_df(self.df)
        self.assertIn("surname_norm", df_norm.columns)
        self.assertIn("plz_prefix2", df_norm.columns)
        self.assertEqual(df_norm.iloc[0]["surname_norm"], "muller")
        self.assertEqual(df_norm.iloc[1]["surname_norm"], "mueller")
        self.assertEqual(df_norm.iloc[0]["plz_prefix2"], "12")

    def test_settings(self):
        settings = get_settings()
        self.assertIn("comparisons", settings)
        self.assertIn("blocking_rules_to_generate_predictions", settings)

    def test_pipeline_simulation(self):
        # 1. Simulate Stage (Writing Parquet)
        df_norm = preprocess_df(self.df)
        df_norm['unique_id'] = range(len(df_norm))

        # Shard keys need to be in the dataframe if we are to use them in Splink settings (additional_columns_to_retain)
        def get_shard(plz):
            if pd.isna(plz) or plz == "": return "no_plz"
            plz_str = str(plz)
            if len(plz_str) >= 2: return plz_str[:2]
            return "no_plz"
        df_norm['shard_key'] = df_norm['plz_norm'].apply(get_shard)

        # Write shards manually for test
        shard_dir = os.path.join(self.parquet_cache, "shard=12")
        os.makedirs(shard_dir, exist_ok=True)
        # Note: We must retain 'shard_key' in the parquet file because 'stage.py' now keeps it,
        # and settings expect it.
        df_norm[df_norm['shard_key'] == '12'].to_parquet(os.path.join(shard_dir, "data.parquet"), index=False)

        shard_dir_other = os.path.join(self.parquet_cache, "shard=54")
        os.makedirs(shard_dir_other, exist_ok=True)
        df_norm[df_norm['shard_key'] == '54'].to_parquet(os.path.join(shard_dir_other, "data.parquet"), index=False)

        # 2. Run Script
        # We assume inference-only because training might need more data to be stable or just works.
        # But wait, if we run training, it loads from parquet.
        # We need to ensure 'shard_key' is in the parquet files. We just did that.

        cmd = (
            f"python scripts/run_splink_dedupe.py "
            f"--out {self.results_dir} "
            f"--parquet-cache {self.parquet_cache} "
            f"--trained-settings {os.path.join(self.test_dir, 'trained.json')} "
        )

        cmd = f"export PYTHONPATH=$PYTHONPATH:. && {cmd}"

        ret = os.system(cmd)
        self.assertEqual(ret, 0)

if __name__ == "__main__":
    main()
