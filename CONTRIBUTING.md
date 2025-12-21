# Contributing

We welcome contributions to the Dubletten project!

## Development Setup

1.  **Clone & Install**:
    ```bash
    git clone ...
    pip install -r requirements.txt
    ```

2.  **Environment**:
    Create a `.env` file (see `.env.example`) with valid DB credentials or use a local CSV for testing.

3.  **Formatting**:
    We use standard Python formatting. Please ensure your code is clean before submitting.

## Running Tests

There are currently no unit tests (TODO), but you can run a limited sample analysis to verify your changes:

```bash
# Run on 10k records to verify end-to-end flow
python run_optimized_analysis.py --limit 10000 --output test_results.csv
```

## Adding New Blocking Rules

1.  Open `duplicate_checker_optimized.py`.
2.  Locate the `OptimizedBlockingStrategy` class.
3.  Add a new method for your blocking key (e.g., `_create_phone_keys`).
4.  Register it in the `get_blocking_keys` method.

## Debugging

*   Use `--limit 1000` to debug quickly.
*   Check `logs/duplicate_checker.log` for detailed execution traces.
*   Use `--benchmark` to verify performance impacts of your changes.
