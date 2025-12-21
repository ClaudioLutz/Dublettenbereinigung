# Ultra-Fast Duplicate Checker

A high-performance Python tool designed to identify duplicate records in large datasets. Optimized for speed and scalability, it has been tested with datasets of up to 7.5 million records, reducing processing time from days/hours to minutes.

## 🚀 Key Features

*   **Vectorized Operations**: Replaces slow iterative processing with optimized Pandas vector operations, achieving up to 200x speed improvement in blocking key creation.
*   **Parallel Processing**: Utilizes multi-core CPUs to process data blocks in parallel, ensuring near-linear scaling.
*   **Smart Blocking**: Implements efficient blocking strategies (including phonetic blocking for German names) to reduce the number of necessary comparisons by >99.9%.
*   **Multi-Pass Blocking**: Uses a multi-pass strategy (Address Pass + Phonetic/Year Pass) to maximize recall while maintaining performance.
*   **Address-Aware Prefiltering**: Uses normalized address data to pre-filter candidates, improving accuracy for borderline cases.
*   **Fuzzy Matching**: Uses `rapidfuzz` for high-performance approximate string matching.
*   **Splink Integration**: Includes a probabilistic deduplication pipeline using Splink v4 and DuckDB for complex, high-recall scenarios.
*   **Business Logic**: Incorporates specific business rules for German addresses, name handling (including swapped names), and date verification.

## 📋 Prerequisites

*   Python 3.8+
*   SQL Server (for default data loading, though CSV is supported)

## 🛠️ Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

### Environment Variables
The project uses `DEDUPE_DB_*` environment variables for database configuration. Create a `.env` file in the root directory (using `.env.example` as a template):

```bash
DEDUPE_DB_SERVER=localhost
DEDUPE_DB_DATABASE=CAG_Analyse
DEDUPE_DB_USER=sa
DEDUPE_DB_PASSWORD=yourStrong(!)Password
DEDUPE_DB_DRIVER=ODBC Driver 17 for SQL Server
DEDUPE_DB_TRUST_SERVER_CERTIFICATE=yes
DEDUPE_DB_ENCRYPT=true
```

For detailed documentation on input requirements, see [DATA_CONTRACT.md](docs/DATA_CONTRACT.md).

## 🏃 Usage

### Which pipeline should I run?

| Use case | Recommended pipeline | Why |
| :--- | :--- | :--- |
| "Fast results, operational run, 7.5M records" | `python run_optimized_analysis.py` | Optimized blocking + parallel CPU; simple output |
| "Need probabilistic match probabilities + clustering" | `python scripts/run_splink_end2end.py` | EM-trained weights, match probability, clusters |
| "Developing new rules / debugging logic" | See [README_OPTIMIZATION.md](README_OPTIMIZATION.md) | Deep technical reasoning + architecture |

**Default Path**: Start with `QUICK_START.md`, then use the heuristic pipeline (`run_optimized_analysis.py`) unless you specifically need probabilistic scoring or complex clustering.

### Heuristic Pipeline

The main entry point for running the heuristic analysis is `run_optimized_analysis.py`.

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
| `--no-multipass` | Disable the multi-pass blocking strategy (runs only the primary pass). | `False` |
| `--max-block-size <n>` | Maximum size of a block before sub-blocking is triggered. | `1000` |
| `--no-address-aware` | Disable address-aware prefiltering. | `False` |
| `--db-user <user>` | SQL Server username (defaults to Windows Auth if unused). | `None` |
| `--db-password <pwd>` | SQL Server password. | `None` |

### Examples

**Run a benchmark to estimate processing time:**
```bash
python run_optimized_analysis.py --benchmark --limit 100000
```

**Run analysis with stricter matching criteria:**
```bash
python run_optimized_analysis.py --confidence 80.0 --fuzzy-threshold 0.8
```

**Run without multi-pass blocking (faster but lower recall):**
```bash
python run_optimized_analysis.py --no-multipass
```

## 🧠 Splink Probabilistic Deduplication

For scenarios requiring probabilistic matching (e.g., estimating match probabilities based on field-specific weights), this project includes a Splink v4 integration.

### Usage
The Splink pipeline is located in `dedupe_splink/` and can be run via:
```bash
python scripts/run_splink_end2end.py
```
This script handles training, prediction, and cluster generation using DuckDB for efficient processing of large datasets.

## 📊 Output

For a detailed explanation of outputs from both pipelines, see [OUTPUTS.md](docs/OUTPUTS.md).

### Heuristic Output
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
*   `dedupe_splink/`: Probabilistic deduplication module using Splink v4.
*   `scripts/`: Helper scripts for Splink execution (`run_splink_end2end.py`, etc.).
*   `tests/`: Unit and integration tests.
*   `logs/`: Log files (auto-rotated).
*   `performance_comparison.py`: Script to compare the optimized version against legacy implementations.
*   `QUICK_START.md`: A quick guide for immediate usage.
*   `README_OPTIMIZATION.md`: Detailed technical explanation of the optimizations applied.

## 🤝 Troubleshooting

*   **Memory Errors**: If running on a machine with limited RAM, try reducing the `max_block_size` in `duplicate_checker_optimized.py` or disable parallel processing with `--no-parallel`.
*   **Database Connection**: If `data.py` fails, ensure your SQL Server credentials and driver are correctly configured, or switch to CSV input.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📦 Versioning & Compatibility

*   **Python**: 3.8+ required (tested on 3.12)
*   **OS**: Windows (optimized for SQL Server) or Linux (supported via ODBC/Docker)
*   **Key Dependencies**:
    *   `rapidfuzz`: High-performance fuzzy matching
    *   `duckdb`: Embedded analytical database for Splink
    *   `splink` (v4): Probabilistic record linkage
