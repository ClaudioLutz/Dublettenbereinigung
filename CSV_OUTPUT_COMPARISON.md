# CSV Output Format Comparison

## Summary
The dedupe/ module has been updated to output CSV files with the same format as duplicate_checker_optimized.py.

## Output Format

### Columns (in order):
1. **match_id** - Unique identifier for the match (Crefo_Crefo or index_index)
2. **confidence** - Confidence score (0-100)
3. **match_type** - Type of match (exact_normal, exact_swapped, fuzzy_normal, fuzzy_swapped, address_assisted_normal, address_assisted_swapped, phonetic_assisted_normal, phonetic_assisted_swapped)
4. **position** - 'A' or 'B' (indicates which record in the pair)
5. **index** - Original dataframe index
6. **vorname** - First name
7. **name** - Last name
8. **name2** - Second name (Zweitname)
9. **strasse** - Street
10. **hausnummer** - House number
11. **plz** - Postal code
12. **ort** - City
13. **crefo** - Crefo number
14. **geburtstag** - Birth date
15. **jahrgang** - Birth year (Jahrgang)

### Row Format
- **2 rows per match**: Each match creates two rows in the CSV
  - First row: position='A', contains record A data
  - Second row: position='B', contains record B data
  - Both rows share the same match_id, confidence, and match_type

## Files Updated

### dedupe/pipeline.py
1. **_write_results()** function:
   - Changed signature to accept `df: pd.DataFrame` parameter
   - Now creates 2 rows per match instead of 1
   - Extracts full record data from dataframe
   - Formats output to match duplicate_checker_optimized.py exactly

2. **run_pipeline()** function:
   - Updated CSV header to include all 15 columns
   - Passes df_chunk to _write_results() calls

## Benefits
- **Consistency**: Both duplicate detection methods now produce identical output formats
- **Compatibility**: Output files can be used interchangeably with downstream tools
- **Completeness**: All record details are included in the output for easy review
- **Clarity**: Two-row format makes it easy to visually compare matched pairs

## Example Output

```csv
match_id,confidence,match_type,position,index,vorname,name,name2,strasse,hausnummer,plz,ort,crefo,geburtstag,jahrgang
12345_67890,95.5,exact_normal,A,100,Hans,Mueller,,Hauptstrasse,15,8000,Zurich,12345,01.01.1980,1980
12345_67890,95.5,exact_normal,B,250,Hans,Mueller,,Hauptstrasse,15,8000,Zurich,67890,01.01.1980,1980
```
