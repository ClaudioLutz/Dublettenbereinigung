# Pipeline Outputs

This document explains the artifacts and results produced by the Duplicate Checker pipelines.

## 1. Heuristic Pipeline Output

**File:** `duplicates_results.csv` (default) or user-specified via `--output`.

### Schema

| Column | Description |
| :--- | :--- |
| `match_id` | Unique ID for the cluster/pair. Both records in a pair share this ID. |
| `confidence` | Score (0-100) indicating the likelihood of a duplicate. |
| `match_type` | The specific logic rule that triggered the match. |
| `match_rank` | Rank of the match (1 = best match for this record). |
| `...original_cols` | All columns from the original input data. |

### Match Types

*   `exact_normal`: Fields match exactly (ignoring case/whitespace). Highest confidence (100).
*   `exact_swapped`: Fields match exactly but First/Last name are swapped. High confidence (95).
*   `fuzzy_normal`: Fields have minor typos (Levenshtein distance). Confidence 70-90.
*   `fuzzy_swapped`: Fields have typos and are swapped. Confidence 70-85.
*   `address_assisted_normal`: Names are borderline (low similarity) but Address + PLZ are exact matches.
*   `address_assisted_swapped`: Swapped names are borderline but Address + PLZ match.

### Recommended Usage
1.  **High Confidence (>90)**: Safe to auto-merge.
2.  **Medium Confidence (80-90)**: Likely duplicates, low false positive rate.
3.  **Low Confidence (70-80)**: Manual review recommended.

---

## 2. Splink Pipeline Output

**Location:** `dedupe_splink/` output files.

### Artifacts

1.  **`splink_model.json`**: The trained Fellegi-Sunter model settings (saved weights).
2.  **`predictions.parquet`**: Pairwise prediction edges with match probabilities.
3.  **`clusters.csv`**: Mapping of `unique_id` -> `cluster_id`.

### Interpreting Splink Results
*   **Match Probability**: A score from 0.0 to 1.0.
    *   `> 0.95`: Extremely strong match.
    *   `> 0.50`: More likely than not a match.
*   **Clusters**: Splink generates transitive clusters. If A=B and B=C, then A=B=C are in one cluster.

---

## 3. Logs

*   **File:** `logs/duplicate_checker.log`
*   **Rotation:** Logs are rotated on every run, keeping history with timestamps.
*   **Content:** Execution timing, match statistics, and error details.
