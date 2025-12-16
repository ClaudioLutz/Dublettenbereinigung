# Ultra-Fast Duplicate Checker

A high-performance Python tool designed to identify duplicate records in large datasets. Optimized for speed and scalability, it has been tested with datasets of up to 7.5 million records, reducing processing time from days/hours to minutes.

## 🚀 Key Features

*   **Vectorized Operations**: Replaces slow iterative processing with optimized Pandas vector operations, achieving up to 200x speed improvement in blocking key creation.
*   **Parallel Processing**: Utilizes multi-core CPUs to process data blocks in parallel, ensuring near-linear scaling.
*   **Smart Blocking**: Implements efficient blocking strategies (including phonetic blocking for German names) to reduce the number of necessary comparisons by >99.9%.
*   **Fuzzy Matching**: Uses `rapidfuzz` for high-performance approximate string matching.
*   **Business Logic**: Incorporates specific business rules for German addresses, name handling (including swapped names), and date verification.

## 📋 Prerequisites

*   Python 3.8+
*   The following Python packages:
    *   `pandas`
    *   `numpy`
    *   `rapidfuzz`
    *   `unidecode`
    *   `cologne-phonetics`
    *   `sqlalchemy` (for database connection)
    *   `matplotlib` (for data visualization/reporting if used)

## 🛠️ Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  Install the required dependencies:
    ```bash
    pip install pandas numpy rapidfuzz unidecode cologne-phonetics sqlalchemy matplotlib
    ```

## ⚙️ Configuration

### Data Source
The project is currently configured to load data from a SQL Server database via `data.py`.

To use your own data source:
1.  **Option A**: Modify `data.py` to connect to your specific database.
2.  **Option B**: Modify `run_optimized_analysis.py` to load your data (e.g., from a CSV file) into a Pandas DataFrame instead of calling `lade_daten`.

Example for CSV loading in `run_optimized_analysis.py`:
```python
# Replace this:
# df = lade_daten(engine, query)

# With this:
df = pd.read_csv('your_data.csv')
```

## 🏃 Usage

The main entry point for running the analysis is `run_optimized_analysis.py`.

### Basic Run
Process the full dataset with default settings:
```bash
python run_optimized_analysis.py
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--limit <n>` | Process only the first `n` records (useful for testing). | `None` (All) |
| `--confidence <n>` | Minimum confidence score (0-100) to consider a match. | `70.0` |
| `--fuzzy-threshold <n>` | Threshold (0.0-1.0) for fuzzy string matching. | `0.7` |
| `--no-parallel` | Disable parallel processing (run on a single core). | `False` |
| `--benchmark` | Run a performance benchmark on sample sizes before full analysis. | `False` |
| `--output <file>` | Filename for the results CSV. | `duplicates_results.csv` |

### Examples

**Run a benchmark to estimate processing time:**
```bash
python run_optimized_analysis.py --benchmark --limit 100000
```

**Run analysis with stricter matching criteria:**
```bash
python run_optimized_analysis.py --confidence 80.0 --fuzzy-threshold 0.8
```

**Run with lenient matching for finding more potential duplicates:**
```bash
python run_optimized_analysis.py --confidence 60.0 --fuzzy-threshold 0.6
```

## 📊 Output

The script generates a CSV file (default: `duplicates_results.csv`) containing pairs of potential duplicates.

Each match consists of two rows (Record A and Record B) sharing the same `match_id`.
Columns include:
*   `match_id`: Unique identifier for the duplicate pair.
*   `confidence`: The confidence score of the match.
*   `match_type`: Type of match (e.g., `exact_normal`, `fuzzy_swapped`).
*   Original record fields (`vorname`, `name`, `strasse`, etc.).

## ⚡ Performance

Benchmarks on typical hardware (8 cores):
*   **100k records**: ~30 seconds
*   **1M records**: ~2 minutes
*   **7.5M records**: ~15 minutes

*Note: Actual performance depends on hardware specifications, data distribution, and the number of duplicates found.*

## 📁 Project Structure

*   `duplicate_checker_optimized.py`: Core logic containing `UltraFastDuplicateChecker`, blocking strategies, and matching algorithms.
*   `run_optimized_analysis.py`: CLI wrapper to run the analysis.
*   `data.py`: Database connection and data loading utilities.
*   `performance_comparison.py`: Script to compare the optimized version against legacy implementations.
*   `QUICK_START.md`: A quick guide for immediate usage.
*   `README_OPTIMIZATION.md`: Detailed technical explanation of the optimizations applied.

## 🤝 Troubleshooting

*   **Memory Errors**: If running on a machine with limited RAM, try reducing the `max_block_size` in `duplicate_checker_optimized.py` or disable parallel processing with `--no-parallel`.
*   **Database Connection**: If `data.py` fails, ensure your SQL Server credentials and driver are correctly configured, or switch to CSV input.

## 📜 License

[Insert License Here]
