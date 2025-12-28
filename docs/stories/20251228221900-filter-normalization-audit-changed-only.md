# Filter Normalization Audit to Changed Addresses Only

## Summary
Modified `normalization_audit.csv` output to only include rows where `swis_changed = True`, reducing noise and focusing on addresses that were actually corrected by Swisstopo normalization.

## Context / Problem
The normalization audit CSV was including all addresses that either matched Swisstopo references OR had their keys changed. This created a large audit file with many entries that were successfully matched but didn't result in any changes. Users primarily need to review addresses where the normalization actually modified the address keys, as these represent corrections or improvements to the data.

## What Changed
- Modified `_write_audit_log()` function in `dedupe/pipeline.py`
- Changed filter mask from `(match_types != "") | (changed == True)` to `(changed == True)`
- Updated function docstring to reflect new behavior: "Write separate audit log for rows where swis_changed is True"
- Removed unused `match_types` variable from the function

## How to Test
1. Run the deduplication pipeline with Swisstopo normalization enabled:
   ```powershell
   .\run_modular.ps1
   ```
2. Check `normalization_audit.csv` and verify all rows have `swis_changed = True`
3. Verify the audit file is smaller than before (should only contain changed addresses, not all matched addresses)

## Risk / Rollback Notes
**Risk**: Low. This only affects the audit output file, not the actual deduplication logic or results.

**Rollback**: If users need to see all matched addresses (not just changed ones), revert the mask back to:
```python
mask = (match_types != "") | (changed == True)
```

The main deduplication results in `modular_results.csv` are unchanged - they still include all normalization fields for all records.
