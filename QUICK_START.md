# QUICK START: Optimized Duplicate Checker

## 🚀 Immediate Actions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file from the example:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Test with Sample Data
```bash
# Test with 10k records to verify configuration
python run_optimized_analysis.py --limit 10000 --benchmark
```

### 4. Run Full Analysis
```bash
# Process all records
python run_optimized_analysis.py --output duplicates_full.csv
```

## ⚙️ Common Options

```bash
# Run with higher confidence threshold (fewer matches, higher quality)
python run_optimized_analysis.py --confidence 80.0

# Run with more lenient matching (more matches, some false positives)
python run_optimized_analysis.py --confidence 60.0 --fuzzy-threshold 0.6

# Custom output filename
python run_optimized_analysis.py --output my_results.csv
```

## 🐛 Common Issues

*   **OOM (Memory)**: Use `--max-block-size 500`.
*   **DB Connection**: Check `.env` and ensure VPN/Network is active.
*   **No Matches**: Check if `Plz` is missing in your data.

> **Note:** For detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
