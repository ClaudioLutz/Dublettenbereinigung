
import unittest
import pandas as pd
import numpy as np
from duplicate_checker_optimized import OptimizedBlockingStrategy

class TestBaseStrategySubBlocking(unittest.TestCase):

    def test_base_strategy_uses_deterministic_subblocking(self):
        """Test that OptimizedBlockingStrategy uses deterministic sub-blocking instead of naive chunking"""
        # Pass max_block_size=2 to create_blocks directly
        strategy = OptimizedBlockingStrategy()

        # Create data that produces a single large block initially
        # But contains duplicates that should remain together after splitting
        data = {
            'Vorname': ['A', 'A', 'B', 'B', 'C', 'C'], # Pairs of duplicates
            'Name':    ['Ma', 'Ma', 'Mb', 'Mb', 'Mc', 'Mc'], # Pairs
            'Plz':     ['12345']*6,
            'Strasse': ['Main']*6,
            'Geburtstag': ['2000']*6,
            'Jahrgang': [2000]*6
        }
        # Total 6 records.
        # Initial block size 6. max_block_size 2.
        # Split by Name L2:
        # Ma: 2 records. <= 2. Block kept.
        # Mb: 2 records. <= 2. Block kept.
        # Mc: 2 records. <= 2. Block kept.

        df = pd.DataFrame(data)

        # Force max_block_size=2
        blocks = strategy.create_blocks(df, max_block_size=2)

        keys = list(blocks.keys())
        print(f"Keys: {keys}")

        # Verify we have keys with L2 structure
        # Key format from _recursive_sub_block: {base_key}_L2_{chars}
        # base_key is "12345_main" (normalized)

        self.assertTrue(len(keys) >= 3, f"Expected at least 3 blocks, got {len(keys)}")
        self.assertTrue(any('L2_MA' in k for k in keys), "Missing split for Ma")
        self.assertTrue(any('L2_MB' in k for k in keys), "Missing split for Mb")
        self.assertTrue(any('L2_MC' in k for k in keys), "Missing split for Mc")

if __name__ == '__main__':
    unittest.main()
