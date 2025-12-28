# Run the modular dedupe pipeline with Windows Authentication
# Usage: .\run_modular.ps1

# --- Ensure we run from the repo root (so relative paths work) ---
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

# --- Environment variables for Windows Authentication ---
$env:DEDUPE_DB_SERVER   = "PRODSVCREPORT70"
$env:DEDUPE_DB_DATABASE = "CAG_Analyse"
# Leave USER and PASSWORD empty for Windows Authentication
$env:PYTHONPATH = $repoRoot

# --- Inputs / outputs ---
$queryFile = Join-Path $repoRoot "query.sql"
$outFile   = Join-Path $repoRoot "modular_results.csv"

# Optional: Swisstopo normalization (local DuckDB index)
$swisDb  = Join-Path $repoRoot "swisstopo_addresses.duckdb"
$auditOut = Join-Path $repoRoot "normalization_audit.csv"  # written only if swisstopo is enabled

$swisArgs = @()
if (Test-Path $swisDb) {
    $swisArgs += @("--swisstopo-db", $swisDb)
    $swisArgs += @("--norm-audit-out", $auditOut)
} else {
    Write-Host "Swisstopo DB not found at: $swisDb" -ForegroundColor Yellow
    Write-Host "Running without swisstopo normalization." -ForegroundColor Yellow
}

# --- Run the modular pipeline ---
Write-Host "Running modular dedupe pipeline with Windows Authentication..." -ForegroundColor Green
Write-Host "Repo: $repoRoot" -ForegroundColor DarkGray
Write-Host "Server: $env:DEDUPE_DB_SERVER" -ForegroundColor Cyan
Write-Host "Database: $env:DEDUPE_DB_DATABASE" -ForegroundColor Cyan
Write-Host "Query: $queryFile" -ForegroundColor Cyan
Write-Host "Output: $outFile" -ForegroundColor Cyan
if ($swisArgs.Count -gt 0) {
    Write-Host "Swisstopo: enabled ($swisDb)" -ForegroundColor Cyan
    Write-Host "Audit: $auditOut" -ForegroundColor Cyan
} else {
    Write-Host "Swisstopo: disabled" -ForegroundColor Cyan
}
Write-Host ""

if (-not (Test-Path $queryFile)) {
    Write-Host "[ERROR] Query file not found: $queryFile" -ForegroundColor Red
    exit 1
}

# Use the call operator (&) so argument splatting behaves consistently
& python scripts/run_dedupe.py --query-file $queryFile --out $outFile --workers 0 @swisArgs

# --- Check results ---
if (Test-Path $outFile) {
    $rowCount = (Get-Content $outFile | Measure-Object -Line).Lines - 1

    # If your results CSV writes one row per side (A/B), pairs are rowCount/2.
    # If it writes one row per pair, pairs == rowCount. We report both.
    $pairCountIfAB = [int]([math]::Floor($rowCount / 2))

    Write-Host ""
    Write-Host "[SUCCESS] Results written." -ForegroundColor Green
    Write-Host "Rows (excluding header): $rowCount" -ForegroundColor Cyan
    Write-Host "Pairs (if A/B rows): $pairCountIfAB" -ForegroundColor Cyan
    Write-Host "Results saved to: $outFile" -ForegroundColor Cyan

    if (Test-Path $auditOut) {
        $auditRows = (Get-Content $auditOut | Measure-Object -Line).Lines - 1
        Write-Host "Normalization audit saved to: $auditOut (rows: $auditRows)" -ForegroundColor Cyan
    }

    # Show first few results
    Write-Host ""
    Write-Host "First few results:" -ForegroundColor Yellow
    Get-Content $outFile | Select-Object -First 5
} else {
    Write-Host "[ERROR] Output file not created: $outFile" -ForegroundColor Red
    exit 2
}
