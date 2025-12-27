
import unittest
import pandas as pd
import numpy as np
from duplicate_checker_optimized import MultiPassBlockingStrategy

class TestDeterministicSubBlocking(unittest.TestCase):

    def test_recursive_sub_blocking(self):
        """Test that recursive sub-blocking splits large blocks deterministically"""
        strategy = MultiPassBlockingStrategy(max_block_size=2)

        # Create a dataframe that will form a large block (all same PLZ -> street_only, all same street -> street_only key)
        # We need enough records to trigger splitting at various levels

        # 1. Year split
        # 2. Name L1 split
        # 3. Name L2 split
        # 4. Vorname L1 split

        data = {
            'Vorname': ['A', 'A', 'B', 'B', 'C', 'C'],
            'Name':    ['Ma', 'Mb', 'Ma', 'Mb', 'Ma', 'Mb'],
            'Plz':     ['']*6,
            'Strasse': ['Main']*6,
            'Geburtstag': ['2000']*3 + ['2001']*3,
            'Jahrgang': [2000]*3 + [2001]*3
        }
        df = pd.DataFrame(data)

        # Run create_blocks
        blocks = strategy.create_blocks(df)

        # Verify no arbitrary chunks (chk_)
        # We expect splits by Year (Y2000, Y2001)
        # Then by Name L1 (M) - all match
        # Then by Name L2 (Ma, Mb)

        block_keys = list(blocks.keys())

        # Should have keys containing Y2000 and Y2001
        self.assertTrue(any('Y2000' in k for k in block_keys))
        self.assertTrue(any('Y2001' in k for k in block_keys))

        # Should have splits by L2 (Ma, Mb) because M is common
        # In 2000 group: A Ma, A Mb, B Ma -> 3 records -> split
        # In 2001 group: B Mb, C Ma, C Mb -> 3 records -> split

        # Check for L2 keys
        self.assertTrue(any('L2_MA' in k for k in block_keys))
        self.assertTrue(any('L2_MB' in k for k in block_keys))

        # Ensure no "chk_" keys (arbitrary chunking) unless hash collision
        self.assertFalse(any('chk_' in k for k in block_keys), f"Found arbitrary chunks: {block_keys}")

    def test_hash_sub_blocking(self):
        """Test that identical records fall into hash buckets or eventual chunking"""
        strategy = MultiPassBlockingStrategy(max_block_size=2)

        # 4 identical records - should go deep into recursion
        data = {
            'Vorname': ['A']*4,
            'Name':    ['Ma']*4,
            'Plz':     ['']*4,
            'Strasse': ['Main']*4,
            'Geburtstag': ['2000']*4,
            'Jahrgang': [2000]*4
        }
        df = pd.DataFrame(data)

        blocks = strategy.create_blocks(df)
        keys = list(blocks.keys())

        # Should go to Hash bucket (H) or Chunk (chk) if hash collides (identical data collides)
        # Since they are identical, they will have same hash.
        # So they will fall into same bucket.
        # Bucket size > max_size (4 > 2).
        # Fallback to chunking INSIDE the bucket.

        # Expect keys like ..._H{hash}_chk_{i}
        # Or just ..._chk_{i} if logic fallback

        self.assertTrue(any('chk_' in k for k in keys))
        # Verify that we tried hashing (H key present or implied path)
        # Actually my implementation does:
        # bucket_key = ..._H{bucket}
        # if too big -> chunk(bucket_key) -> ..._H{bucket}_chk_{i}

        self.assertTrue(any('_H' in k and '_chk_' in k for k in keys), f"Expected hashed chunks, got {keys}")

if __name__ == '__main__':
    unittest.main()
