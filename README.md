# Swiss Entity Deduplication Library

A high-performance, modular Python library designed for deduplicating large datasets (millions of records) of Swiss entity data. This project employs a multi-stage approach that combines exact matching, address-based blocking with Swisstopo verification, and fuzzy name matching to identify duplicates with high precision.

## Interesting Techniques

The codebase utilizes several advanced techniques to ensure performance and accuracy:

*   **Vectorized String Operations**: To handle millions of records efficiently, the project avoids row-wise operations in favor of Pandas' vectorized string methods for blocking key generation. This significantly speeds up the initial grouping of candidates. See [`dedupe/blocking.py`](dedupe/blocking.py).
*   **Regex-based Parsing**: Complex address cleaning and normalization are handled using compiled regular expressions, allowing for robust extraction of street names and house numbers. See [`dedupe/preprocess.py`](dedupe/preprocess.py). [MDN: Regular Expressions](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions)
*   **Concurrency with Worker Threads**: The pipeline processes data chunks in parallel using `ThreadPoolExecutor`, implementing a semaphore-like pattern to manage memory usage while maximizing CPU utilization. See [`dedupe/pipeline.py`](dedupe/pipeline.py). [MDN: Web Workers API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API) (Conceptual parallel)
*   **Phonetic Algorithms**: To catch audible duplicates (e.g., "Meier" vs "Meyer"), the system employs the Cologne Phonetics algorithm, which is specifically optimized for German names. See [`dedupe/scoring.py`](dedupe/scoring.py).
*   **Embedded Analytical Database**: Integration with DuckDB allows for high-speed, local querying of the massive Swisstopo address register without the overhead of a traditional database server. See [`dedupe/swisstopo.py`](dedupe/swisstopo.py).

## Non-obvious Technologies

Beyond the standard data science stack, this project leverages specific libraries for specialized tasks:

*   **[DuckDB](https://duckdb.org/)**: An in-process SQL OLAP database management system used here for fast address verification against the Swisstopo dataset.
*   **[RapidFuzz](https://github.com/maxbachmann/RapidFuzz)**: A fast string matching library that uses Levenshtein distance. It is used as a higher-performance replacement for FuzzyWuzzy.
*   **[Unidecode](https://pypi.org/project/Unidecode/)**: A library that transliterates Unicode text into ASCII, essential for normalizing names with special characters before comparison.
*   **[Cologne Phonetics](https://pypi.org/project/cologne-phonetics/)**: A phonetic algorithm similar to Soundex but optimized for the German language.
*   **[SQLAlchemy](https://www.sqlalchemy.org/)** with **[PyODBC](https://github.com/mkleehammer/pyodbc)**: Provides robust connectivity to MS SQL Server, handling connection pooling and dialect differences.

## Project Structure

```
/
├── dedupe/                 # Core package containing deduplication logic
├── docs/                   # Documentation and business rules
├── legacy/                 # Quarantined legacy code and scripts
├── scripts/                # Entry points and utility scripts
├── tests/                  # Unit and integration tests
├── query.sql               # Example SQL query for data extraction
├── requirements.txt        # Project dependencies
└── run_modular.ps1         # PowerShell entry point for Windows
```

*   **`dedupe/`**: The heart of the application. It splits responsibilities into clear modules: `blocking` for reducing the search space, `scoring` for detailed comparison, and `pipeline` for orchestration.
*   **`scripts/`**: Contains the executable scripts to run the deduplication process or build necessary indices (like the Swisstopo index).
*   **`legacy/`**: Holds older implementations (like the initial Splink-based approach) that are preserved for reference but not part of the active pipeline.
