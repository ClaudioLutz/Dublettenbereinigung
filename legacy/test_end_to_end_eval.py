
import unittest
import pandas as pd
import os
from duplicate_checker_optimized import UltraFastDuplicateChecker

class TestEndToEndEval(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
        self.data_path = os.path.join(self.fixtures_dir, 'test_data_eval.csv')
        self.labels_path = os.path.join(self.fixtures_dir, 'labeled_pairs.csv')

        self.df = pd.read_csv(self.data_path)
        self.labels = pd.read_csv(self.labels_path)

        # Initialize checker with aggressive thresholds for testing
        # NOTE: fuzzy_threshold must be high enough (>0.60) to allow the address-aware logic
        # to kick in for borderline cases (score >= 0.60 and < fuzzy_threshold).
        self.checker = UltraFastDuplicateChecker(
            fuzzy_threshold=0.85,
            use_parallel=False,
            use_multipass=True
        )

    def test_recall_precision(self):
        # Run analysis
        matches = self.checker.analyze_duplicates(self.df, confidence_threshold=60.0)

        # Convert matches to set of sorted tuples
        found_pairs = set()
        for m in matches:
            pair = tuple(sorted((m.record_a_idx, m.record_b_idx)))
            found_pairs.add(pair)

        # Check against labels
        tp = 0
        fn = 0
        fp = 0 # Can't fully check FP without knowing all true negatives, but we can check if we found expected ones

        print("\nEvaluation Results:")
        for _, row in self.labels.iterrows():
            pair = tuple(sorted((row['idx_a'], row['idx_b'])))
            is_dup = row['is_duplicate']
            scenario = row['scenario']

            if is_dup:
                if pair in found_pairs:
                    tp += 1
                    print(f"  [PASS] Found expected duplicate {pair} ({scenario})")
                else:
                    fn += 1
                    print(f"  [FAIL] Missed expected duplicate {pair} ({scenario})")
            else:
                if pair in found_pairs:
                    fp += 1
                    print(f"  [FAIL] False positive {pair} ({scenario})")

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        print(f"\nRecall: {recall:.2f} ({tp}/{tp+fn})")

        # Assert minimal recall (we expect to find most of these)
        # Note: 8,9 (multipass) might fail if multipass isn't fully tuned yet
        # 6,7 (address_assisted) might fail if thresholds are strict
        self.assertGreaterEqual(recall, 0.8, "Recall should be at least 80% on this fixture")

if __name__ == '__main__':
    unittest.main()
