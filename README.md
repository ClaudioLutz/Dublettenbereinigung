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

##  architecture

The supported CLI entrypoint for this project is `scripts/run_dedupe.py`. The supported package API is the `dedupe` package, which contains the core deduplication pipeline and its components.

## ⚙️ Configuration

### Data Source
The project is configured to load data from a SQL Server database using environment variables. See the "Secrets & Environment" section for details. The `scripts/run_dedupe.py` script accepts a SQL query file as input.

## 🏃 Usage

The main entry point for running the deduplication pipeline is `scripts/run_dedupe.py`.

### Basic Run
Process the full dataset with default settings:
```bash
python scripts/run_dedupe.py --query-file query.sql --out duplicates.csv
```

### Command Line Arguments

| Argument | Description |
|---|---|
| `--query-file` | Path to the SQL query file. |
| `--out` | Output CSV path. |
| `--workers` | Number of worker threads (0=auto). |
| `--prompt-password` | Prompt for DB password instead of using env var. |

### Examples

**Run with a specific query file and output path:**
```bash
python scripts/run_dedupe.py --query-file my_query.sql --out my_duplicates.csv
```

**Run with 4 worker threads:**
```bash
python scripts/run_dedupe.py --query-file query.sql --out duplicates.csv --workers 4
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

## 🔐 Secrets & Environment

The project loads database credentials from environment variables. Create a `.env` file based on `.env.example` (if available) or set the following:

```
DB_SERVER=your-sql-host
DB_DATABASE=your-db
DB_USER=your-user
DB_PASSWORD=your-password
DB_DRIVER=ODBC Driver 17 for SQL Server     # optional
DB_TRUST_SERVER_CERTIFICATE=yes             # optional
```

## 🤝 Troubleshooting

*   **Memory Errors**: If running on a machine with limited RAM, try reducing the `max_block_size` in `duplicate_checker_optimized.py` or disable parallel processing with `--no-parallel`.
*   **Database Connection**: If `data.py` fails, ensure your SQL Server credentials and driver are correctly configured, or switch to CSV input.

## 📜 License

[Insert License Here]
