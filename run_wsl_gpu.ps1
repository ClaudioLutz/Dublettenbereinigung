# PowerShell script to run deduplication with GPU in WSL2
# Usage: .\run_wsl_gpu.ps1
#
# Two-step process:
# 1. Export data from SQL to parquet (Windows - has SQL auth)
# 2. Run GPU deduplication in WSL (Linux - has cuML)

$QueryFile = "query.sql"
$OutputFile = "results_ml_gpu.csv"
$ParquetFile = "results_ml_gpu.parquet"
$EmbeddingsDir = "models/embeddings"

# Step 1: Export from SQL to parquet (Windows)
Write-Host "Step 1: Exporting data from SQL to parquet..." -ForegroundColor Cyan
& venv\Scripts\python.exe scripts\run_dedupe.py --query-file $QueryFile --out $OutputFile --export-only
if ($LASTEXITCODE -ne 0) {
    Write-Host "Export failed!" -ForegroundColor Red
    exit 1
}

# Step 2: Run GPU deduplication in WSL
Write-Host "`nStep 2: Running ML deduplication with GPU in WSL2..." -ForegroundColor Cyan
wsl -d Ubuntu-22.04 -- bash -c "source /home/claudio/miniforge3/etc/profile.d/conda.sh && conda activate rapids-dedupe && cd /mnt/c/Lokal_Code/dubletten && python scripts/run_dedupe.py --input-file $ParquetFile --out $OutputFile --use-ml-scoring --embeddings-dir $EmbeddingsDir --use-gpu"

Write-Host "`nDone!" -ForegroundColor Green
