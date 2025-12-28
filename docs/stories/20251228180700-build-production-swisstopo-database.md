# Build Production Swisstopo Address Database

**Date:** 2025-12-28 18:07:00 UTC+1  
**Type:** Production Data Setup

## Summary

Built the production swisstopo address normalization database from the complete Swiss address register (3.28M addresses), replacing the example database that was previously used for testing.

## Context / Problem

The swisstopo address normalization feature was initially developed and tested using a small example CSV file with only 15 sample addresses (`swisstopo_example.duckdb`). This example database was sufficient for:
- Unit testing the normalization logic
- Verifying the build script functionality
- Testing integration with the pipeline

However, for production use with real deduplication tasks, the full Swiss address register is required to:
- Normalize addresses across all of Switzerland (not just the example addresses)
- Maximize the match rate for address-based blocking
- Provide accurate canonical address representations
- Enable proper address typo recovery

## What Changed

### 1. Built Production Database

**Input:**
- Full Swiss address register CSV: `amtliches-gebaeudeadressverzeichnis_ch_2056.csv`
- File size: 465,119,687 bytes (~443 MB)
- Record count: 3,279,825 addresses

**Output:**
- Production database: `swisstopo_addresses.duckdb`
- File size: 506,736,640 bytes (~483 MB)
- Record count: 3,279,825 addresses (all with status='real' or 'planned')
- Unique PLZ: 3,181 postal codes

**Command used:**
```bash
python scripts/build_swisstopo_index.py
```

This uses the default settings which automatically:
- Read from: `amtliches-gebaeudeadressverzeichnis_ch_2056.csv/amtliches-gebaeudeadressverzeichnis_ch_2056.csv`
- Write to: `swisstopo_addresses.duckdb`
- Filter to only 'real' and 'planned' addresses

### 2. Database Statistics

**Coverage:**
- 3,279,825 total addresses
- 3,181 unique postal codes (PLZ4)
- All Swiss cantons represented
- Real and planned addresses only (construction/provisional excluded)

**Structure:**
- Primary index: `(plz4, street_key, house_num)` for strict matching
- Secondary index: `(plz4, street_sig, house_num)` for typo recovery
- Tertiary index: `(plz4)` for PLZ-level queries

**Fields stored:**
- Join keys: `plz4`, `street_key`, `street_sig`, `house_num`
- Reference values: `street_label`, `adr_number`, `ort`
- IDs: `adr_egaid`, `bdg_egid`, `com_fosnr`, `com_name`, `com_canton`
- Metadata: `adr_status`, `adr_official`

## How to Test

### 1. Verify Database Structure

```bash
python -c "import duckdb; con = duckdb.connect('swisstopo_addresses.duckdb'); print(con.execute('SELECT COUNT(*), COUNT(DISTINCT plz4) FROM addresses').fetchone())"
```

Expected output: `(3279825, 3181)`

### 2. Test Address Lookup

```bash
python -c "
import duckdb
con = duckdb.connect('swisstopo_addresses.duckdb')
result = con.execute('''
    SELECT street_label, adr_number, ort 
    FROM addresses 
    WHERE plz4='8000' AND street_key='bahnhof'
    LIMIT 5
''').fetchall()
for row in result:
    print(row)
"
```

Expected: Returns addresses from Zurich with normalized street containing 'bahnhof'

### 3. Run Production Deduplication

```bash
python scripts/run_dedupe.py `
  --query-file query.sql `
  --out results_with_full_swisstopo.csv `
  --swisstopo-db swisstopo_addresses.duckdb
```

Expected:
- Pipeline loads successfully
- Shows "Swisstopo normalization: enabled" in run summary
- Prints database statistics (3.28M addresses, 3,181 PLZ)
- Processes addresses with normalization
- Output includes addresses normalized to canonical forms

### 4. Compare Match Rates

Run the same deduplication with and without swisstopo normalization and compare:
- Number of candidate pairs generated
- Number of matches found
- Specific cases where normalization helped (e.g., "Hofstatt Str." → "Hofstattstrasse")

## Risk / Rollback Notes

### Risks

1. **Increased disk usage**: Production database is 483 MB vs 50 KB for example
   - **Impact**: Minimal on modern systems
   - **Mitigation**: Database is optional; can be deleted if not needed

2. **Longer load time**: Loading 3.28M addresses takes longer than 15 addresses
   - **Impact**: ~1-2 seconds at pipeline startup
   - **Mitigation**: Connection is persistent for duration of pipeline run
   - **Mitigation**: DuckDB memory-maps the file, so actual RAM usage is minimal

3. **Different match behavior**: Production data may normalize addresses differently than example data
   - **Impact**: Match rates may increase (good) but specific test expectations may change
   - **Mitigation**: Example database still exists for unit tests
   - **Mitigation**: Can use `--swisstopo-db swisstopo_example.duckdb` for testing

4. **Data freshness**: Database snapshot is from December 28, 2025
   - **Impact**: New addresses added after this date won't be in the reference
   - **Mitigation**: Rebuild periodically using same command
   - **Mitigation**: Non-matched addresses fall back to basic normalization

### Rollback Steps

If issues arise with the production database:

1. **Use example database for testing:**
   ```bash
   python scripts/run_dedupe.py --swisstopo-db swisstopo_example.duckdb ...
   ```

2. **Disable swisstopo normalization:**
   ```bash
   python scripts/run_dedupe.py --query-file query.sql --out results.csv
   # (omit --swisstopo-db parameter)
   ```

3. **Delete production database:**
   ```bash
   rm swisstopo_addresses.duckdb
   ```

4. **Rebuild from scratch if corrupted:**
   ```bash
   python scripts/build_swisstopo_index.py
   ```

### Build Performance

- **CSV read time**: ~10 seconds
- **Normalization time**: ~30 seconds
- **Index creation time**: ~40 seconds
- **Total build time**: ~80 seconds (1-2 minutes)

### Storage Requirements

- Input CSV: 443 MB
- Output DuckDB: 483 MB
- **Total storage**: ~926 MB (can keep CSV archived/compressed)

## Next Steps for Production Use

1. **Run comprehensive deduplication** with production database
2. **Monitor match statistics** to verify improved coverage
3. **Document match rate improvements** vs. non-normalized approach
4. **Set up periodic rebuild** schedule (e.g., quarterly when swisstopo releases updates)
5. **Consider archiving or compressing** the source CSV to save space
6. **Add database to .gitignore** (already done) to avoid committing 483 MB file

## Usage Example

```bash
# Production run with full swisstopo normalization
python scripts/run_dedupe.py `
  --query-file query.sql `
  --out production_results.csv `
  --swisstopo-db swisstopo_addresses.duckdb `
  --chunk-size 200000

# Expected console output:
# Loading swisstopo address database from swisstopo_addresses.duckdb...
# ✓ Loaded 3,279,825 addresses (3,181 unique PLZ)
# Swisstopo normalization: enabled
# Processing addresses with reference-based normalization...
```

## Database Maintenance

### When to Rebuild

- **Quarterly**: When swisstopo releases updated address register
- **After major changes**: If Switzerland adds new postal codes or major developments
- **On corruption**: If database file becomes corrupted (rare)

### How to Update

1. Download latest swisstopo CSV
2. Replace existing CSV file
3. Run: `python scripts/build_swisstopo_index.py`
4. Verify statistics match expected record count

### Backup Strategy

- **Keep source CSV**: Always maintain the source CSV file
- **Version databases**: Optionally rename by date (e.g., `swisstopo_addresses_20251228.duckdb`)
- **Compress archived versions**: Use zip/gzip for long-term storage
