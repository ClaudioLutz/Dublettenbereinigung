# Ultra-Fast Duplicate Checker

A high-performance Python tool designed to identify duplicate records in large datasets using a modular, vectorized pipeline. Optimized for speed and scalability, it has been tested with datasets of up to 7.5 million records, reducing processing time from days/hours to minutes.

## 🚀 Key Features

*   **Vectorized Operations**: Replaces slow iterative processing with optimized Pandas vector operations, achieving significant speed improvements in blocking key creation.
*   **Parallel Processing**: Utilizes multi-core CPUs to process data blocks in parallel, ensuring near-linear scaling.
*   **Smart Blocking**: Implements efficient blocking strategies (Address-based and Name-based) to reduce the number of necessary comparisons by >99.9%.
*   **Multi-Pass Blocking**: Uses a multi-pass strategy to maximize recall while maintaining performance.
*   **Address-Aware Prefiltering**: Uses normalized address data to pre-filter candidates, improving accuracy for borderline cases.
*   **Swisstopo Normalization**: Optional integration with Swisstopo data for reference-based address normalization.
*   **Fuzzy Matching**: Uses `rapidfuzz` for high-performance approximate string matching.
*   **Business Logic**: Incorporates specific business rules for German addresses, name handling (including swapped names), and date verification.

## 📋 Prerequisites

*   Python 3.8+
*   SQL Server (for default data loading)
*   DuckDB (optional, for Swisstopo normalization)

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

## 🏗️ Architecture

The project is structured around the `dedupe` package, which contains the core deduplication pipeline. The CLI entry point is located in `scripts/`.

### Project Structure

*   `dedupe/`: Core package containing the deduplication logic.
    *   `pipeline.py`: Main processing pipeline.
    *   `blocking.py`: Blocking strategies.
    *   `candidates.py`: Candidate generation and matching.
    *   `swisstopo.py`: Swisstopo integration.
*   `scripts/`: Command-line tools.
    *   `run_dedupe.py`: Main entry point for the deduplication pipeline.
    *   `build_swisstopo_index.py`: Tool to build the Swisstopo normalization index.
*   `legacy/`: Legacy scripts and previous implementations (including Splink integration).
*   `tests/`: Unit and integration tests.
*   `docs/`: Documentation.

## ⚙️ Configuration

### Data Source
The project is configured to load data from a SQL Server database using environment variables. Create a `.env` file or set the following environment variables (note the `DEDUPE_DB_` prefix):

```bash
DEDUPE_DB_SERVER=your-sql-host
DEDUPE_DB_DATABASE=your-db
DEDUPE_DB_USER=your-user                 # Optional for Windows Auth
DEDUPE_DB_PASSWORD=your-password         # Optional for Windows Auth
DEDUPE_DB_DRIVER=ODBC Driver 17 for SQL Server
DEDUPE_DB_TRUST_SERVER_CERTIFICATE=true  # Optional (default: true)
DEDUPE_DB_ENCRYPT=true                   # Optional (default: true)
```

## 🏃 Usage

The main entry point for running the deduplication pipeline is `scripts/run_dedupe.py`.

### Basic Run
Process the dataset with default settings (Address-based blocking):
```bash
python scripts/run_dedupe.py --query-file query.sql --out duplicates.csv
```

### Command Line Arguments

| Argument | Description |
|---|---|
| `--query-file` | Path to the SQL query file (Required). |
| `--out` | Output CSV path (Required). |
| `--workers` | Number of worker threads (0=auto). |
| `--blocking-mode` | Blocking strategy: `address` (default) or `name`. |
| `--fuzzy-threshold` | Fuzzy name similarity threshold (default: 0.80). |
| `--window-size` | Window size for sorted neighborhood (default: 10). |
| `--no-address-aware` | Disable address-assisted matching. |
| `--swisstopo-db` | Path to Swisstopo DuckDB file for normalization (optional). |
| `--norm-audit-out` | Path to write normalization audit CSV (optional). |
| `--prompt-password` | Prompt for DB password instead of using env var. |

### Examples

**Run with Name-based blocking (legacy mode):**
```bash
python scripts/run_dedupe.py --query-file query.sql --out duplicates.csv --blocking-mode name
```

**Run with Swisstopo normalization enabled:**
```bash
python scripts/run_dedupe.py --query-file query.sql --out duplicates.csv --swisstopo-db swisstopo.duckdb
```

## 🕰️ Legacy & Alternative Methods

### Splink Probabilistic Deduplication
The project previously explored a probabilistic deduplication pipeline using Splink v4. These scripts are now located in the `legacy/` directory.
*   `legacy/run_splink_end2end.py`: End-to-end Splink pipeline.
*   `legacy/run_splink_train.py`: Splink model training.
*   `legacy/run_splink_predict.py`: Splink prediction.

### Legacy Scripts
Older versions of the deduplication logic (e.g., `duplicate_checker_optimized.py`) are also preserved in `legacy/` for reference.

## 📊 Output

The script generates a CSV file containing pairs of potential duplicates.
Columns include:
*   `match_id`: Unique identifier for the duplicate pair.
*   `confidence`: The confidence score of the match.
*   `match_type`: Type of match (e.g., `exact_normal`, `fuzzy_swapped`).
*   Original record fields.
*   Address normalization metadata (if enabled).

## ⚡ Performance

Benchmarks on typical hardware (8 cores) for the optimized pipeline:
*   **100k records**: ~30 seconds
*   **1M records**: ~2 minutes
*   **7.5M records**: ~15 minutes

*Note: Actual performance depends on hardware specifications, data distribution, and the blocking strategy used.*

## 📜 License

[Insert License Here]
