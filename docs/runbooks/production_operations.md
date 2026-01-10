# Production Operations Runbook

## Overview

This runbook provides operational procedures for the Tier Assignment System (Stage 3) of the dubletten deduplication pipeline.

## 1. Deployment Checklist

### Prerequisites

- Python 3.9+ installed
- Required packages: pandas, pyyaml, numpy
- Optional: psutil (for memory monitoring)
- Access to input directory containing:
  - `clustered_results.csv`
  - `llm_labeled_results.csv`

### Installation Steps

1. Clone repository:
   ```bash
   git clone <repository-url>
   cd dubletten
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Verify installation:
   ```bash
   python -m pytest tests/test_pipeline_integration.py -q
   ```

### Validation Steps

1. Run with test data:
   ```bash
   python scripts/generate_tiered_output.py --input-dir _bmad-output/analysis/run_<timestamp>
   ```

2. Verify outputs exist:
   - `auto_merge_pairs.csv` (Tier 1)
   - `review_queue_pairs.csv` (Tier 2)

3. Check Excel compatibility - open CSV files in Excel and verify German characters display correctly.

## 2. Monitoring Procedures

### Key Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Stage 3 Runtime | <5 min | >5 min |
| Memory Usage | <8 GB | >8 GB |
| Tier 1 Percentage | 20-28% | <15% or >35% |
| Total Pairs | Expected count | >20% deviation |

### Normal vs Abnormal Values

**Normal Operation:**
- Tier 1 count: ~20,000-25,000 pairs
- Tier 2 count: ~45,000-55,000 pairs
- Runtime: 30 seconds - 3 minutes
- Memory: 500 MB - 2 GB

**Abnormal Indicators:**
- Zero Tier 1 pairs (all going to review)
- Runtime >10 minutes
- Memory >8 GB
- Error messages in logs

### Log Monitoring

Logs are written with Python logging module:
- INFO: Normal operation, stage transitions
- WARNING: Non-critical issues
- ERROR: Critical issues requiring attention

## 3. Troubleshooting Guide

### Common Issues and Solutions

#### Issue: "File not found: clustered_results.csv"

**Root Cause:** Stage 2 did not complete or output directory is incorrect.

**Resolution:**
1. Verify Stage 2 completed successfully
2. Check `--input-dir` path is correct
3. Look for latest run directory: `ls -la _bmad-output/analysis/`

#### Issue: "Missing required columns"

**Root Cause:** Input file format changed or corrupted.

**Resolution:**
1. Verify clustered_results.csv has columns: i, j, score, cluster
2. Verify llm_labeled_results.csv has columns: i, j, cluster, llm_label
3. Re-run Stage 2 if files are corrupted

#### Issue: All pairs in Tier 2 (zero Tier 1)

**Root Cause:** All clusters have >0% false positive rate.

**Resolution:**
1. Review LLM validation results
2. Check cluster_labels_v1.yaml configuration
3. Consider re-running LLM validation with more samples

#### Issue: Performance degradation (runtime >10 min)

**Root Cause:** Large dataset or system resource contention.

**Resolution:**
1. Check system memory availability
2. Verify no other heavy processes running
3. Consider splitting large datasets

### Error Message Interpretations

| Error Message | Meaning | Action |
|---------------|---------|--------|
| "Invalid cluster values" | Cluster ID outside 0-14 range | Check Stage 2 clustering |
| "Data loss detected" | Tier 1 + Tier 2 != Total | Bug - escalate |
| "YAML syntax error" | Config file corrupted | Restore from git |

## 4. Rollback Procedures

### YAML Configuration Rollback

1. List previous versions:
   ```bash
   git log --oneline config/cluster_labels_v1.yaml
   ```

2. Restore previous version:
   ```bash
   git checkout <commit-hash> -- config/cluster_labels_v1.yaml
   ```

### Model Version Rollback

1. List available models:
   ```bash
   ls -la models/cluster_model_*.yaml
   ```

2. Update config to use previous model:
   - Edit config/cluster_labels_v1.yaml
   - Change model_version reference

### Full Pipeline Rollback

1. Identify last working commit:
   ```bash
   git log --oneline
   ```

2. Create rollback branch:
   ```bash
   git checkout -b rollback-<date> <commit-hash>
   ```

3. Re-run tests:
   ```bash
   python -m pytest tests/test_pipeline_integration.py -q
   ```

## 5. Escalation Process

### When to Escalate

Escalate to Data Science team when:
- All clusters show >0% FP rate
- Data integrity validation fails
- Performance issues persist after troubleshooting
- Unexpected behavior not covered in this runbook

### Escalation Information to Gather

Before escalating, collect:
1. Error messages and log output
2. Input file statistics (row counts, cluster distribution)
3. System resource usage (memory, CPU)
4. Recent configuration changes

### Contact Information

- Data Science Team: [internal contact]
- On-call Engineer: [internal contact]
- Issue Tracker: [internal tracker URL]

## Appendix: Quick Reference

### Run Commands

```bash
# Full pipeline with auto-discovery
python scripts/generate_tiered_output.py

# With specific input directory
python scripts/generate_tiered_output.py --input-dir _bmad-output/analysis/run_20260110

# With YAML config
python scripts/generate_tiered_output.py --input-dir <dir> --config config/cluster_labels_v1.yaml
```

### Output Files

| File | Description |
|------|-------------|
| auto_merge_pairs.csv | Tier 1: 0% FP rate clusters |
| review_queue_pairs.csv | Tier 2: >0% FP rate clusters |
| tier_report.md | Validation report (if enabled) |

### Performance Targets

| Metric | Target |
|--------|--------|
| Stage 3 Runtime | <5 minutes |
| Memory Usage | <8 GB |
| Classification | <10 min for 78k pairs |
