# HOW TO FIND ALL DUPLICATES IN YOUR 7.5 MILLION RECORDS

## 🔴 THE PROBLEM

Your `data.py` query has **`TOP (1000)`** which only loads 1,000 rows instead of 7.5 million!

That's why:
- ✗ It runs in 10 seconds (too fast!)
- ✗ You only get 2 duplicates instead of 100,000
- ✗ Only 1,013 records are processed

## ✅ THE SOLUTION

### Step 1: Fix the Query in data.py

Open `data.py` and change line 54 from:

```sql
SELECT TOP (1000) [Name]
```

To:

```sql
SELECT [Name]
```

**Remove the `TOP (1000)` completely!**

Optionally, you can also adjust the date filter if needed. Current query:
```sql
Where Erfasst < dateadd(day,-7,getdate())
```

### Step 2: Run the Full Pipeline

After fixing the query, run:

```bash
python scripts\run_splink_end2end.py --use-data-py --threshold 0.75
```

**Note**: With 7.5 million records, this will take much longer (hours, not seconds!)
- The `--threshold 0.75` means records must be 75% similar to be considered duplicates
- Lower threshold = more duplicates found (but also more false positives)
- Higher threshold = fewer duplicates found (but more accurate)

### Step 3: Generate the Duplicate Report with Names and Addresses

After the pipeline finishes, run:

```bash
python generate_duplicate_report.py
```

This will create:
- **`duplicate_report.csv`** - Full list with names, addresses, etc.
- **`duplicate_report.xlsx`** - Excel version (if openpyxl is installed)

## 📊 WHAT THE OUTPUT MEANS

### cluster_mapping.csv
- `unique_id`: The ID of each record
- `cluster_id`: Records with the SAME cluster_id are duplicates

Example:
```
unique_id,cluster_id
48,48          ← These 2 records are duplicates
49,48          ← (same cluster_id = 48)
100,100        ← This record has no duplicates
101,55         ← These 3 records are duplicates
102,55         ← (same cluster_id = 55)
103,55         ←
```

### duplicate_report.csv
This shows the actual duplicate records with:
- cluster_id (which group of duplicates)
- records_in_cluster (how many duplicates in this group)
- Name, Vorname, Strasse, PLZ, Ort, etc.
- All the original data fields

**Open this in Excel to see all your duplicates with names and addresses!**

## ⚙️ PERFORMANCE TIPS FOR 7.5 MILLION RECORDS

If the pipeline is too slow or runs out of memory:

### Option 1: Process in Batches
Instead of removing `TOP (1000)`, use a larger number and process in batches:
```sql
SELECT TOP (500000) [Name]  -- 500K at a time
```

### Option 2: Add More Filters
Add WHERE conditions to focus on specific records:
```sql
Where Erfasst < dateadd(day,-7,getdate())
  AND Plz IS NOT NULL  -- Only records with postal codes
  AND Name IS NOT NULL  -- Only records with names
```

### Option 3: Adjust Memory/Threads
Run with more memory and threads:
```bash
python scripts\run_splink_end2end.py --use-data-py --threshold 0.75 --memory-limit 16GB --threads 8
```

## 📝 CURRENT TEST DATA RESULT

With your current TOP (1000) test data, the script found:
- **Total records**: 1,013
- **Duplicates found**: 2 records (1 duplicate pair)
- **Example duplicate pair:**
  - Record 48: Oberli Georges, Avenue de Cour 130, 100700 Lausanne
  - Record 49: Oberlé Georges, Chemin des Croix-Rouges 14, 100700 Lausanne

These are correctly identified as duplicates (similar names, same PLZ prefix).

## ❓ COMMON QUESTIONS

**Q: Why does the threshold matter?**
- `0.95` = 95% similar (very strict, fewer duplicates)
- `0.75` = 75% similar (more lenient, more duplicates)
- `0.50` = 50% similar (very lenient, many false positives)

**Q: Can I see the similarity score for each duplicate pair?**
Yes! Check the files in `output_splink/edges/` - these contain match probabilities.

**Q: What if I want to review before marking as duplicates?**
The `duplicate_report.csv` shows all potential duplicates. Review it manually to decide which ones are real duplicates.

## 🚀 QUICK START FOR FULL DATA

1. Edit `data.py` - remove `TOP (1000)`
2. Run: `python scripts\run_splink_end2end.py --use-data-py --threshold 0.75`
3. Wait (this will take hours for 7.5M records)
4. Run: `python generate_duplicate_report.py`
5. Open `duplicate_report.csv` or `duplicate_report.xlsx`

**That's it! You'll have your complete list of ~100,000 duplicates with names and addresses!**
