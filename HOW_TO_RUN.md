# How to Run the Duplicate Checker

This project has **two ways** to run duplicate detection. Both work with Windows Authentication.

---

## ✅ Option 1: Modular Pipeline (Recommended - Just Ran Successfully!)

The modular pipeline is a newer, streaming architecture.

### Quick Run
```powershell
.\run_modular.ps1
```

### Manual Run
```powershell
$env:DEDUPE_DB_SERVER="PRODSVCREPORT70"
$env:DEDUPE_DB_DATABASE="CAG_Analyse"
$env:PYTHONPATH="c:\Lokal_Code\dubletten"
python scripts/run_dedupe.py --query-file query.sql --out modular_results.csv
```

### Output Format
The modular pipeline produces a CSV with these columns:
- `i`, `j`: Record indices of the duplicate pair
- `score`: Overall match confidence (0-100)
- `name_score`: Name similarity score
- `addr_score`: Address similarity score  
- `reason`: Match reason code

### Customize the Query
Edit `query.sql` to change what data to process:
- Remove `TOP (1000)` to process all records
- Adjust the date filter in the WHERE clause
- Add more fields if needed

---

## ✅ Option 2: Original Optimized Pipeline

The original high-performance pipeline with detailed output.

### Quick Run
```bash
# Test with 100K records first
python run_optimized_analysis.py --limit 100000 --benchmark

# Run full analysis
python run_optimized_analysis.py --output duplicates_results.csv
```

### Options
```bash
# Higher confidence (fewer, better matches)
python run_optimized_analysis.py --confidence 80.0

# More lenient (find more potential duplicates)
python run_optimized_analysis.py --confidence 60.0 --fuzzy-threshold 0.6

# Disable parallel processing
python run_optimized_analysis.py --no-parallel

# Custom output
python run_optimized_analysis.py --output my_results.csv
```

### Output Format
The original pipeline produces detailed pair records:
- `match_id`: Unique ID for each duplicate pair
- `confidence`: Match confidence score
- `match_type`: Type of match (exact, fuzzy, swapped names, etc.)
- All original record fields for both records

---

## 🔧 Key Differences

| Feature | Modular Pipeline | Original Pipeline |
|---------|------------------|-------------------|
| **Output** | Compact (indices + scores) | Detailed (full records) |
| **Speed** | Fast, streaming | Very fast, in-memory |
| **Memory** | Low | Moderate |
| **Best for** | Large datasets, indices | Review, analysis |
| **Status** | ✅ Just ran successfully! | Production ready |

---

## 📁 Important Files

- **query.sql** - SQL query for data loading (modular pipeline)
- **run_modular.ps1** - PowerShell script to run modular pipeline
- **run_optimized_analysis.py** - Main script for original pipeline
- **modular_results.csv** - Output from modular pipeline (just created!)
- **duplicates_results.csv** - Output from original pipeline

---

## 💡 Tips

1. **Start with modular pipeline** for quick tests (we just did this!)
2. **Use original pipeline** when you need detailed record information
3. **Test with small samples** before processing millions of records
4. **Adjust confidence thresholds** based on your data quality needs
5. **Check the output** to ensure matches look correct

---

## ✅ What We Just Did

We successfully ran the modular pipeline with:
- Windows Authentication (no password needed)
- Query from `query.sql` (1000 records)
- Output: `modular_results.csv` (found 1 duplicate pair)
- Score: 84.0 overall (92.9 name match, 63.3 address match)

To process more data, edit `query.sql` and remove the `TOP (1000)` limit!
