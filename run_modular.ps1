# Run the modular dedupe pipeline with Windows Authentication
# Usage: .\run_modular.ps1

# Set environment variables for Windows Authentication
$env:DEDUPE_DB_SERVER="PRODSVCREPORT70"
$env:DEDUPE_DB_DATABASE="CAG_Analyse"
# Leave USER and PASSWORD empty for Windows Authentication
$env:PYTHONPATH="c:\Lokal_Code\dubletten"

# Run the modular pipeline
Write-Host "Running modular dedupe pipeline with Windows Authentication..." -ForegroundColor Green
Write-Host "Server: $env:DEDUPE_DB_SERVER" -ForegroundColor Cyan
Write-Host "Database: $env:DEDUPE_DB_DATABASE" -ForegroundColor Cyan
Write-Host ""

python scripts/run_dedupe.py --query-file query.sql --out modular_results.csv --workers 0

# Check results
if (Test-Path modular_results.csv) {
    $count = (Get-Content modular_results.csv | Measure-Object -Line).Lines - 1
    Write-Host ""
    Write-Host "[SUCCESS] Found $count duplicate pair(s)" -ForegroundColor Green
    Write-Host "Results saved to: modular_results.csv" -ForegroundColor Cyan
    
    # Show first few results
    Write-Host ""
    Write-Host "First few results:" -ForegroundColor Yellow
    Get-Content modular_results.csv | Select-Object -First 5
} else {
    Write-Host "[ERROR] Output file not created" -ForegroundColor Red
}
