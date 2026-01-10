---
stepsCompleted: [1, 2, 3, 4]
workflowStatus: complete
totalEpics: 7
totalStories: 26
inputDocuments:
  - docs/planing-artefacts/prd.md
  - docs/architecture.md
  - docs/END_TO_END_PIPELINE.md
  - docs/businessrules.md
---

# dubletten - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the Pattern Discovery & Tiering System, decomposing the requirements from the PRD, Architecture, and END_TO_END_PIPELINE into implementable stories.

## Requirements Inventory

### Functional Requirements

**FR1: Tier Assignment System**
- FR1.1: Generate Tiered Outputs - Read clustered results, assign pairs to Tier 1 (0% FP) or Tier 2 (>0% FP), generate separate CSV outputs
- FR1.2: Cluster Label Mapping - Load cluster-to-tier mapping from YAML config, support updates without code changes, validate completeness
- FR1.3: Validation Reporting - Generate tier assignment report with statistics, FP rates, cluster distribution

**FR2: Model Persistence**
- FR2.1: Export K-Modes Model - Export k-modes cluster centroids to YAML format with version control
- FR2.2: Load Model from YAML - Load k-modes model at startup, validate version compatibility, graceful degradation on failure
- FR2.3: Cluster Classification - Classify pairs by comparing feature vectors to cluster centroids using Hamming distance

**FR3: Ground Truth Management**
- FR3.1: Save Validated Pairs - Save LLM-validated pairs to ground_truth/ directory organized by category
- FR3.2: Regression Testing - Load ground truth in test suite, assert score ranges match historical behavior

**FR4: Production Integration**
- FR4.1: Cluster Classifier Module - Provide dedupe/cluster_classifier.py with classify_pair() and classify_batch() functions
- FR4.2: End-to-End Pipeline Integration - Integrate Stage 3 (tier assignment) with existing Stage 1 and Stage 2, maintain ≤90 min runtime
- FR4.3: Output File Format - Auto-merge and review queue CSVs with match_id, cluster, confidence, UTF-8 with BOM encoding

**FR5: Monitoring & Observability**
- FR5.1: Runtime Monitoring - Log classification time, tier generation time, memory usage, performance warnings
- FR5.2: Quality Monitoring - Track auto-merge volume over time, alert on volume drops or cluster size changes
- FR5.3: Error Handling - Log all errors with stack traces, continue on non-critical errors, halt on critical errors

**FR6: Quarterly Re-Clustering Workflow**
- FR6.1: Re-Clustering Execution - Support manual re-clustering via CLI, generate new model version, preserve previous for rollback
- FR6.2: Validation Comparison - Compare new FP rates to previous, highlight changed clusters, generate migration guide

**FR7: Business Reporting**
- FR7.1: ROI Dashboard - Calculate FTE hours saved, track LLM costs, compute net ROI annually
- FR7.2: Executive Summary - Generate quarterly summary with volume, FP rate, efficiency gains, exportable to PDF

### Non-Functional Requirements

**NFR1: Performance**
- NFR1.1: Runtime Performance - End-to-end pipeline ≤90 min, cluster classification ≤10 min, tier assignment ≤5 min, model loading ≤30 sec
- NFR1.2: Scalability - Handle up to 10M records, support up to 200k matched pairs, support up to 30 clusters
- NFR1.3: Resource Usage - Peak memory ≤16GB RAM, CPU usage ≤80% average, streaming I/O to avoid bottlenecks

**NFR2: Reliability**
- NFR2.1: Availability - 99% pipeline success rate, graceful degradation on model load failure
- NFR2.2: Data Integrity - All CSVs pass schema validation, Tier 1 pairs validated against 0% FP guarantee
- NFR2.3: Fault Tolerance - Missing YAML defaults to Tier 2, corrupt validation triggers warning, continue on non-critical errors

**NFR3: Maintainability**
- NFR3.1: Code Quality - PEP 8 style, docstrings with type hints, ≥80% code coverage for critical modules
- NFR3.2: Configuration Management - All config externalized to YAML, no hard-coded values, version compatibility validation
- NFR3.3: Documentation - Comprehensive API docstrings, README with setup/usage/troubleshooting, runbooks for operations

**NFR4: Operability**
- NFR4.1: Deployment - ≤30 min deployment time, rollback via git revert + model downgrade, zero downtime not required
- NFR4.2: Monitoring - All errors logged with severity, performance metrics per run, alerts on FP rate/volume/runtime issues
- NFR4.3: Debuggability - Logs with timestamps/severity/module/context, error messages with remediation steps, trace IDs across stages

**NFR5: Security**
- NFR5.1: Data Privacy - PII masked in logs, ground truth with restricted permissions, encrypted HTTPS for LLM API
- NFR5.2: Access Control - Model YAML read-only for pipeline, config files require admin privileges, ground truth writable only by pipeline
- NFR5.3: API Security - API key in environment variables, rate limiting and circuit breaker, response validation

**NFR6: Usability**
- NFR6.1: CLI Interface - Clear help text, progress indicators, actionable error messages
- NFR6.2: Output Formats - Excel-compatible CSV (UTF-8 BOM), plain text reports, browser-viewable dashboards

**NFR7: Compliance & Auditability**
- NFR7.1: Audit Trail - Every auto-merge traceable to cluster + validation date, model version logged per run
- NFR7.2: Reproducibility - Same input + model = identical outputs, fixed random seeds, pinned dependencies
- NFR7.3: Validation Evidence - LLM validation results preserved, ground truth immutable, cluster FP rates documented

### Additional Requirements

**From Architecture:**
- Existing Pipeline Architecture: Stage 1 (dedupe/pipeline.py) generates modular_results.csv, Stage 2 (pattern_discovery.py) generates clustered_results.csv
- Technology Stack: Python 3.9+, NumPy, Pandas, PyYAML, kmodes, RapidFuzz, pytest
- Prohibited Dependencies: No pickle files (security/compatibility), no GPU-only libraries, no external databases for model storage
- Infrastructure: Windows Server 2019+ OR Linux Ubuntu 20.04+, CPU-only execution, 16GB RAM minimum
- Backward Compatibility: Stage 1 output format must not change, existing merge tools must work with new CSV outputs
- Blocking Strategy: Address-based blocking (PLZ + street + house), sorted neighborhood method (window size 10)
- Business Rules: 35+ Swiss-specific business rules with gender-aware logic, DOB gates, compound surnames
- Scoring Module: dedupe/scoring.py with score_pair() function, match types (exact_normal, exact_swapped, fuzzy_normal, fuzzy_swapped, address_assisted, phonetic_assisted)

**From END_TO_END_PIPELINE:**
- Stage 3 Implementation Gap: Missing scripts/generate_tiered_output.py to generate tiered outputs based on cluster FP rates
- Integration Requirements: Stage 2 outputs (clustered_results.csv, llm_labeled_results.csv) feed into Stage 3
- Output File Requirements: auto_merge_pairs.csv (Tier 1: 0% FP, ~20k pairs), review_queue_pairs.csv (Tier 2: manual review, ~45k pairs)
- Cluster Performance Validated: 11 clusters with 0% FP rate (Clusters 3,4,6,7,8,9,10,11,12,13,14), 4 clusters with >0% FP rate
- Business Goal: "Get closest to 100% cluster and deduplicate them automatically, provide accurate scores for manual review, maximize Tier 1 size without false positives"
- Current Pipeline Runtime: Stage 1 ~60 min, Stage 2 classification ~8-10 min, Stage 3 target <5 min (total ≤90 min)
- Ground Truth Structure: clear_duplicates.csv, clear_non_duplicates.csv, edge_cases.csv in ground_truth/ directory
- Pattern Discovery Phases: Phase 1 (clustering), Phase 2 (LLM validation), Phase 3 (tier assignment), Phase 4 (continuous improvement)
- File Structure: Models in models/, configs in config/, ground truth in ground_truth/, outputs in _bmad-output/analysis/

**From Business Rules:**
- 35+ boolean rule features extracted from matched pairs for clustering
- Business rule gates: DOB mismatch, YOB mismatch, different buildings (immediate rejection)
- Soft gates: Gender mismatch penalty (-20 points) for siblings/spouses at same address
- Match type confidence ranges: exact_normal (90-100%), exact_swapped (85-100%), fuzzy_normal (40-95%), address_assisted (70-80%), phonetic_assisted (72-82%)
- Pattern Discovery workflow: Phase 1 (clustering), Phase 2 (LLM calibration), Phase 3 (full analysis), Phase 4 (continuous improvement)
- Ground truth categories: clear_duplicates, clear_non_duplicates, edge_cases, boundary_cases
- Regression testing: pytest tests/test_business_rules.py validates scoring consistency

### FR Coverage Map

```
FR1.1 (Generate Tiered Outputs) → Epic 1
FR1.2 (Cluster Label Mapping) → Epic 1
FR1.3 (Validation Reporting) → Epic 4
FR2.1 (Export K-Modes Model) → Epic 2
FR2.2 (Load Model from YAML) → Epic 2
FR2.3 (Cluster Classification) → Epic 1
FR3.1 (Save Validated Pairs) → Epic 5
FR3.2 (Regression Testing) → Epic 5
FR4.1 (Cluster Classifier Module) → Epic 2
FR4.2 (End-to-End Pipeline Integration) → Epic 3
FR4.3 (Output File Format) → Epic 2
FR5.1 (Runtime Monitoring) → Epic 4
FR5.2 (Quality Monitoring) → Epic 4
FR5.3 (Error Handling) → Epic 4
FR6.1 (Re-Clustering Execution) → Epic 6
FR6.2 (Validation Comparison) → Epic 6
FR7.1 (ROI Dashboard) → Epic 7
FR7.2 (Executive Summary) → Epic 7

NFR1 (Performance) → Epic 3
NFR2 (Reliability) → Epic 3
NFR3 (Maintainability) → Epic 5
NFR4 (Operability) → Epic 4
NFR5 (Security) → Epic 4
NFR6 (Usability) → Epic 4
NFR7 (Compliance & Auditability) → Epic 5
```

## Epic List

### Epic 1: Automated Tier Assignment System
Data quality analysts can generate separate auto-merge and review queues with 0% false positive guarantee, reducing manual review workload by 40%.

**User Outcome**: Anna receives two distinct output files - high-confidence auto-merge pairs (Tier 1: 0% FP rate) and lower-confidence review pairs (Tier 2) - enabling her to confidently execute automated merges while focusing manual review on genuinely ambiguous cases.

**FRs covered**: FR1.1, FR1.2, FR2.3

---

### Epic 2: Production-Ready Model Persistence
DevOps engineers can deploy the tier assignment system with YAML-based configs, graceful degradation, and zero ML runtime dependencies.

**User Outcome**: Lena can deploy and maintain the system using familiar version-controlled YAML files, with clear error messages and rollback strategies, without dealing with pickle files or GPU dependencies.

**FRs covered**: FR2.1, FR2.2, FR4.1, FR4.3

---

### Epic 3: End-to-End Pipeline Integration
Operations teams can run the complete pipeline (Stage 1 + Stage 2 + Stage 3) seamlessly from raw data to tiered outputs in under 90 minutes.

**User Outcome**: The full deduplication pipeline runs end-to-end, with Stage 3 (tier assignment) integrated into the existing architecture, maintaining performance targets and backward compatibility.

**FRs covered**: FR4.2, NFR1, NFR2

---

### Epic 4: Monitoring & Operational Observability
Operations and management teams have visibility into system performance, quality metrics, and potential issues through comprehensive logging, monitoring, and alerting.

**User Outcome**: Lena and Thomas can monitor pipeline health, track auto-merge volume trends, receive alerts when patterns change, and troubleshoot issues with clear error messages and remediation guidance.

**FRs covered**: FR5.1, FR5.2, FR5.3, FR1.3, NFR4, NFR5, NFR6

---

### Epic 5: Ground Truth Management & Continuous Improvement
Data quality managers build a growing library of ground truth pairs that serve as regression tests and compliance evidence, enabling systematic improvement over time.

**User Outcome**: Thomas accumulates validated pairs (LLM-validated duplicates and non-duplicates) as immutable regression tests, ensuring that rule changes don't break previously validated behavior and providing audit evidence for compliance.

**FRs covered**: FR3.1, FR3.2, NFR3, NFR7

---

### Epic 6: Quarterly Re-Clustering Workflow
Data quality managers can re-run pattern discovery quarterly to adapt to data evolution, with clear migration guides and validation comparisons.

**User Outcome**: Thomas can refresh cluster models quarterly, compare new patterns to previous validations, identify clusters with changed FP rates, and update production configs with confidence through clear migration guides.

**FRs covered**: FR6.1, FR6.2

---

### Epic 7: Business Intelligence & ROI Reporting
Executive stakeholders receive comprehensive quarterly reports demonstrating ROI, efficiency gains, quality metrics, and team satisfaction.

**User Outcome**: Dr. Weber can demonstrate ROI with quarterly dashboards showing FTE hours saved, auto-merge volume, false positive rates, LLM costs, and team morale - enabling data-driven decisions about scaling the system.

**FRs covered**: FR7.1, FR7.2

---

## Epic 1: Automated Tier Assignment System

Data quality analysts can generate separate auto-merge and review queues with 0% false positive guarantee, reducing manual review workload by 40%.

### Story 1.1: Generate Tiered Output Files from Clustered Results

As a data quality analyst,
I want the system to read clustered results and LLM validation data and generate separate CSV files for auto-merge (Tier 1) and review queue (Tier 2),
So that I can confidently execute automated merges for high-confidence pairs while focusing manual review on ambiguous cases.

**Acceptance Criteria:**

**Given** clustered_results.csv exists with cluster assignments (0-14) and llm_labeled_results.csv exists with FP rates per cluster
**When** I run the tier assignment script
**Then** the system generates auto_merge_pairs.csv containing only pairs from clusters with 0% FP rate
**And** the system generates review_queue_pairs.csv containing all other pairs
**And** both files include columns: match_id, cluster, confidence, and all original record fields
**And** files are UTF-8 with BOM encoding for Excel compatibility
**And** Tier 1 file contains approximately 18k-22k pairs (validated clusters: 3,4,6,7,8,9,10,11,12,13,14)
**And** Tier 2 file contains remaining pairs (~45k-50k)

---

### Story 1.2: Load Cluster-to-Tier Mapping from YAML Configuration

As a DevOps engineer,
I want the tier assignment logic to load cluster-to-tier mappings from a YAML configuration file,
So that I can update tier assignments without code changes when cluster validation results change.

**Acceptance Criteria:**

**Given** a YAML configuration file exists at config/cluster_labels_v1.yaml
**When** the tier assignment script starts
**Then** the system loads the cluster-to-tier mapping (cluster ID → Tier 1 or Tier 2)
**And** the system validates that all 15 clusters (0-14) are mapped
**And** unmapped clusters trigger a warning and default to Tier 2 (safe fallback)
**And** the system logs the loaded configuration version and cluster count
**And** invalid YAML format triggers a clear error message with remediation guidance

---

### Story 1.3: Classify Pairs by Cluster Using Hamming Distance

As a data quality analyst,
I want each matched pair to be assigned to a cluster based on its rule activation pattern,
So that the tier assignment system can route pairs to the correct confidence tier.

**Acceptance Criteria:**

**Given** a matched pair has 35 boolean rule features extracted
**When** the cluster classifier processes the pair
**Then** the system compares the feature vector to all cluster centroids using Hamming distance
**And** the system assigns the pair to the cluster with minimum Hamming distance
**And** the system adds a 'cluster' column (integer 0-14) to the results
**And** classification completes in ≤10 minutes for 78k pairs
**And** the system logs classification time and cluster distribution statistics

---

### Story 1.4: Generate Tier Assignment Validation Report

As a data quality manager,
I want a tier assignment report showing statistics, cluster distribution, and FP rates,
So that I can verify the auto-merge tier has 0% false positive rate and review tier size is manageable.

**Acceptance Criteria:**

**Given** tiered outputs have been generated successfully
**When** the tier assignment completes
**Then** the system generates a tier_report.md file in _bmad-output/analysis/run_{timestamp}/
**And** the report includes: Tier 1 count, Tier 2 count, cluster distribution per tier
**And** the report includes: validation date, FP rates per cluster, silhouette score
**And** the report includes: auto-merge percentage (Tier 1 / Total), manual review reduction percentage
**And** the report is readable in plain text editors
**And** the report includes cluster profiles (centroids) for each Tier 1 cluster

---

## Epic 2: Production-Ready Model Persistence

DevOps engineers can deploy the tier assignment system with YAML-based configs, graceful degradation, and zero ML runtime dependencies.

### Story 2.1: Export K-Modes Cluster Model to YAML Format

As a data scientist,
I want to export the trained k-modes cluster centroids to a YAML file with semantic versioning,
So that the production system can load the model without pickle files or ML dependencies.

**Acceptance Criteria:**

**Given** a trained k-modes clustering model exists with 15 clusters and 35 features
**When** I run the model export script
**Then** the system exports cluster centroids to models/cluster_model_v1.yaml
**And** the YAML includes: cluster count (15), feature names (35 features), centroid values (0 or 1 per feature)
**And** the YAML includes metadata: creation date, validation date, silhouette score, model version
**And** the YAML file is valid and parses without errors
**And** the file is version-controlled with semantic versioning (v1, v2, v3...)
**And** the system validates YAML schema on export and logs success confirmation

---

### Story 2.2: Load K-Modes Model from YAML with Graceful Degradation

As a DevOps engineer,
I want the production pipeline to load the k-modes model from YAML at startup with graceful degradation if the file is missing,
So that deployment failures are predictable and the system defaults to safe behavior.

**Acceptance Criteria:**

**Given** the cluster classifier module is initialized
**When** the system starts up
**Then** the system attempts to load models/cluster_model_v1.yaml
**And** if the file exists and is valid, the model loads successfully in ≤30 seconds
**And** the system validates model version compatibility with code version
**And** if the file is missing, the system logs a warning and defaults all pairs to Tier 2 (safe fallback)
**And** if the file is corrupt, the system logs an error with remediation guidance and defaults to Tier 2
**And** the system logs model loading status (success/failure), version, cluster count, and feature count

---

### Story 2.3: Implement Cluster Classifier Module with No ML Dependencies

As a DevOps engineer,
I want a dedupe/cluster_classifier.py module that classifies pairs using pure Python and NumPy,
So that production deployment doesn't require GPU, pickle files, or ML libraries.

**Acceptance Criteria:**

**Given** the cluster_classifier.py module exists
**When** I call classify_pair(features) or classify_batch(pairs_df)
**Then** the module returns cluster ID (0-14) using Hamming distance comparison to centroids
**And** the module uses only Python 3.9+, NumPy, and Pandas (no kmodes library dependency)
**And** the module loads YAML configs at import time
**And** classification is deterministic (same input always produces same cluster assignment)
**And** batch classification processes 78k pairs in ≤10 minutes on CPU-only execution
**And** the module includes docstrings with type hints for all public functions

---

### Story 2.4: Define Tiered Output CSV File Format with Excel Compatibility

As a data quality analyst,
I want the auto-merge and review queue CSV files to be Excel-compatible with clear column headers,
So that I can open and work with the files in Excel and existing merge tools.

**Acceptance Criteria:**

**Given** the tier assignment has completed
**When** I open auto_merge_pairs.csv or review_queue_pairs.csv
**Then** both files use UTF-8 encoding with BOM for Excel compatibility
**And** both files include columns: match_id, cluster, confidence, i, j, and all original record fields (Vorname, Name, Strasse, PLZ, Ort, etc.)
**And** match_id format is {Crefo_A}_{Crefo_B} for unique pair identification
**And** cluster column contains integer 0-14
**And** confidence column contains float 0-100 (original score from Stage 1)
**And** files are compatible with existing merge tools (same schema as modular_results.csv)
**And** file encoding errors do not occur when opening in Excel or LibreOffice

---

## Epic 3: End-to-End Pipeline Integration

Operations teams can run the complete pipeline (Stage 1 + Stage 2 + Stage 3) seamlessly from raw data to tiered outputs in under 90 minutes.

### Story 3.1: Integrate Stage 3 Tier Assignment into Existing Pipeline

As an operations engineer,
I want Stage 3 (tier assignment) to run automatically after Stage 2 (clustering) completes,
So that the full pipeline runs end-to-end from raw data to tiered outputs without manual intervention.

**Acceptance Criteria:**

**Given** Stage 1 (deduplication) and Stage 2 (clustering) have completed successfully
**When** the end-to-end pipeline runs
**Then** Stage 3 (tier assignment) starts automatically after Stage 2
**And** Stage 3 reads clustered_results.csv from Stage 2 output directory
**And** Stage 3 reads llm_labeled_results.csv from Stage 2 output directory (or uses cached version)
**And** Stage 3 generates tiered outputs in the same _bmad-output/analysis/run_{timestamp}/ directory
**And** total pipeline runtime (Stage 1 + 2 + 3) is ≤90 minutes
**And** Stage 3 adds <5 minutes to the total runtime
**And** pipeline logs show clear stage transitions and completion status

---

### Story 3.2: Maintain Backward Compatibility with Existing Merge Tools

As a data quality analyst,
I want the new tiered output files to work with our existing merge tools and workflows,
So that I don't have to change our downstream processes.

**Acceptance Criteria:**

**Given** existing merge tools expect modular_results.csv format (2 rows per match with position A/B)
**When** I use the tiered output files
**Then** auto_merge_pairs.csv and review_queue_pairs.csv maintain the same column schema
**And** match_id format is identical to existing format
**And** existing tools can load and process the files without errors
**And** Stage 1 output format (modular_results.csv) remains unchanged
**And** existing tests in tests/test_business_rules.py continue to pass
**And** no breaking changes to dedupe/scoring.py or dedupe/pipeline.py

---

### Story 3.3: Validate Performance Targets Across Full Pipeline

As an operations engineer,
I want to verify that the integrated pipeline meets performance targets across all stages,
So that monthly production runs complete within the acceptable time window.

**Acceptance Criteria:**

**Given** a full pipeline run on 7.5M records
**When** I measure performance across all stages
**Then** Stage 1 (deduplication) completes in ≤60 minutes
**And** Stage 2 (clustering + classification) completes in ≤10 minutes
**And** Stage 3 (tier assignment) completes in ≤5 minutes
**And** total end-to-end runtime is ≤90 minutes
**And** peak memory usage is ≤16GB RAM
**And** CPU usage averages ≤80% during processing
**And** performance metrics are logged per stage with timestamps

---

### Story 3.4: Implement Reliability Checks and Data Integrity Validation

As a data quality manager,
I want the pipeline to validate data integrity at each stage and fail fast on critical errors,
So that we catch data quality issues early and don't waste time on invalid results.

**Acceptance Criteria:**

**Given** the pipeline is running
**When** each stage completes
**Then** the system validates output CSV schema (column names, data types)
**And** the system validates Tier 1 pairs against 0% FP guarantee (all clusters have validated 0% FP rate)
**And** the system validates no data loss occurred (total pairs in Tier 1 + Tier 2 = input pairs)
**And** the system validates cluster assignments are valid (0-14 range)
**And** critical errors (missing input files, corrupt data, schema violations) halt the pipeline immediately
**And** non-critical errors (warnings) are logged but pipeline continues
**And** final validation report is generated showing all integrity checks passed

---

## Epic 4: Monitoring & Operational Observability

Operations and management teams have visibility into system performance, quality metrics, and potential issues through comprehensive logging, monitoring, and alerting.

### Story 4.1: Implement Runtime Performance Monitoring

As an operations engineer,
I want the pipeline to log runtime performance metrics for each stage,
So that I can identify bottlenecks and performance degradation over time.

**Acceptance Criteria:**

**Given** the pipeline is running
**When** each stage executes
**Then** the system logs: start time, end time, elapsed time per stage
**And** the system logs: cluster classification time per batch (target: ≤10 min for 78k pairs)
**And** the system logs: tier generation time (target: ≤5 min)
**And** the system logs: memory usage (current, peak) during classification
**And** the system logs: CPU usage average during processing
**And** the system logs warnings if performance degrades >10% from baseline
**And** logs include timestamps, severity level (INFO/WARNING), and module name

---

### Story 4.2: Implement Quality Monitoring and Alerting

As a data quality manager,
I want the system to track auto-merge volume trends and alert me when patterns change unexpectedly,
So that I can investigate potential data quality issues or model drift.

**Acceptance Criteria:**

**Given** the pipeline completes successfully
**When** quality monitoring analyzes the results
**Then** the system tracks auto-merge volume over time (Tier 1 pair count per run)
**And** the system alerts if auto-merge volume drops >20% between runs
**And** the system tracks cluster size distribution changes
**And** the system alerts if any cluster grows >50% between quarterly runs
**And** the system tracks Tier 1 / Total pairs percentage (target: 20-28%)
**And** alerts are logged with severity level (WARNING/ERROR) and remediation guidance
**And** alert thresholds are configurable in YAML config

---

### Story 4.3: Implement Comprehensive Error Handling with Remediation Guidance

As an operations engineer,
I want clear error messages with remediation steps when something goes wrong,
So that I can quickly resolve issues without escalating to data science team.

**Acceptance Criteria:**

**Given** an error occurs during pipeline execution
**When** the system encounters the error
**Then** the system logs the error with: timestamp, severity level (ERROR/CRITICAL), module, message, stack trace
**And** error messages include remediation guidance (e.g., "File not found: models/cluster_model_v1.yaml. Run export script or restore from git.")
**And** the system continues on non-critical errors (missing optional configs, low-severity warnings)
**And** the system halts immediately on critical errors (missing input files, corrupt data, model load failure with no fallback)
**And** PII is masked in all log outputs (names, addresses, DOBs)
**And** logs are written to _bmad-output/logs/ with rotation (max 10 files, 100MB per file)

---

### Story 4.4: Create Production Runbook with Troubleshooting Guide

As an operations engineer,
I want a comprehensive runbook documenting deployment, monitoring, and troubleshooting procedures,
So that I can operate the system independently and resolve common issues quickly.

**Acceptance Criteria:**

**Given** the production system is deployed
**When** I reference the runbook documentation
**Then** the runbook includes: deployment checklist (prerequisites, installation steps, validation)
**And** the runbook includes: monitoring procedures (what to monitor, normal vs abnormal metrics)
**And** the runbook includes: troubleshooting flowchart (common issues → root causes → resolutions)
**And** the runbook includes: rollback procedure (how to revert YAML configs, model versions)
**And** the runbook includes: escalation process (when to contact data science team)
**And** the runbook is stored in docs/runbooks/production_operations.md
**And** the runbook is reviewed and validated by operations team

---

## Epic 5: Ground Truth Management & Continuous Improvement

Data quality managers build a growing library of ground truth pairs that serve as regression tests and compliance evidence, enabling systematic improvement over time.

### Story 5.1: Save LLM-Validated Pairs to Ground Truth Directory

As a data quality manager,
I want LLM-validated pairs to be automatically saved to the ground_truth/ directory organized by category,
So that we accumulate a regression test suite and compliance evidence over time.

**Acceptance Criteria:**

**Given** Phase 2 LLM validation has completed with labeled pairs
**When** the validation finishes
**Then** the system saves validated pairs to ground_truth/clear_duplicates.csv (pairs labeled DUPLICATE with confidence ≥0.85)
**And** the system saves validated pairs to ground_truth/clear_non_duplicates.csv (pairs labeled NOT_DUPLICATE with confidence ≥0.85)
**And** the system saves validated pairs to ground_truth/edge_cases.csv (pairs with confidence <0.85)
**And** each entry includes: pair IDs (i, j), cluster, LLM label, confidence, validation date, original record fields
**And** the system appends to existing files (does not overwrite)
**And** ground truth files are stored with restricted file permissions (read-only for pipeline, writable only by admin)
**And** the system logs the count of pairs saved per category

---

### Story 5.2: Implement Regression Testing Framework with Ground Truth

As a data quality manager,
I want automated regression tests that validate scoring behavior matches historical ground truth,
So that business rule changes don't break previously validated patterns.

**Acceptance Criteria:**

**Given** ground truth files exist with validated pairs
**When** I run pytest tests/test_business_rules.py
**Then** the test suite loads all pairs from ground_truth/ directory
**And** tests assert that clear duplicates still score within expected ranges (e.g., ≥60%)
**And** tests assert that clear non-duplicates still score below rejection thresholds
**And** tests assert that edge cases maintain consistent behavior
**And** tests fail if rule changes cause validated pairs to change classification
**And** test failures generate a diff report showing behavioral changes
**And** tests run in <5 minutes for 800+ ground truth pairs

---

### Story 5.3: Create Comprehensive Documentation for System Maintenance

As a data quality manager,
I want comprehensive documentation covering architecture, business rules, and maintenance procedures,
So that new team members can understand and maintain the system.

**Acceptance Criteria:**

**Given** the system is production-ready
**When** I review the documentation
**Then** docs/END_TO_END_PIPELINE.md is updated with Stage 3 tier assignment details
**And** docs/architecture.md includes cluster classifier module and YAML persistence
**And** docs/businessrules.md documents pattern discovery workflow and ground truth management
**And** all public module APIs have comprehensive docstrings with type hints
**And** README.md includes: setup instructions, usage examples, troubleshooting common issues
**And** a story file is created per CLAUDE.md requirements documenting the Pattern Discovery system implementation
**And** cluster-to-tier mapping rationale is documented in models/cluster_labels_v1.yaml comments

---

### Story 5.4: Implement Audit Trail for Compliance and Reproducibility

As a compliance officer,
I want every auto-merge decision to be traceable to its cluster validation and model version,
So that we can demonstrate regulatory compliance and reproduce results for audits.

**Acceptance Criteria:**

**Given** auto-merge pairs are generated
**When** I audit the decisions
**Then** every Tier 1 pair includes: cluster ID, validation date, model version used
**And** the tier_report.md includes: cluster FP rates, LLM validation sample size, validation methodology
**And** model version is logged in pipeline execution logs for each run
**And** configuration changes are tracked in git history with commit messages
**And** given the same input data and model version, the pipeline produces identical outputs (reproducibility)
**And** random seeds are fixed for reproducible clustering
**And** all dependencies are pinned to specific versions in requirements.txt
**And** LLM validation results are preserved in _bmad-output/analysis/run_{timestamp}/llm_labeled_results.csv

---

## Epic 6: Quarterly Re-Clustering Workflow

Data quality managers can re-run pattern discovery quarterly to adapt to data evolution, with clear migration guides and validation comparisons.

### Story 6.1: Implement Manual Re-Clustering CLI Command

As a data quality manager,
I want a CLI command to trigger quarterly re-clustering that generates a new model version,
So that I can refresh cluster models when data patterns evolve.

**Acceptance Criteria:**

**Given** new deduplication results are available
**When** I run `python -m dedupe.analysis.pattern_discovery --phase reclustering --clusters 15`
**Then** the system runs Phase 1 (k-modes clustering) on the new data
**And** the system runs Phase 2 (LLM validation) with 175 stratified samples
**And** the system exports a new model version (e.g., models/cluster_model_v2.yaml)
**And** the system preserves the previous model version (cluster_model_v1.yaml remains unchanged)
**And** the system generates a new cluster labels config (config/cluster_labels_v2.yaml)
**And** the system creates a validation comparison report comparing v1 vs v2 FP rates
**And** total re-clustering cost is ≤$0.50 (DeepSeek API)

---

### Story 6.2: Generate Migration Guide Comparing Old and New Validation Results

As a data quality manager,
I want a migration guide that compares new cluster FP rates to previous validation,
So that I can understand what changed and update production configs confidently.

**Acceptance Criteria:**

**Given** re-clustering has completed with new model version
**When** I review the migration guide
**Then** the guide shows side-by-side comparison: Cluster ID, v1 FP rate, v2 FP rate, change (↑↓→)
**And** the guide highlights clusters where FP rate changed (0% → >0% or >0% → 0%)
**And** the guide recommends tier mapping updates (e.g., "Move Cluster 5 from Tier 1 to Tier 2 due to FP rate increase")
**And** the guide includes: silhouette score comparison (v1 vs v2), cluster size distribution changes
**And** the guide includes: validation sample statistics (sample size, LLM cost, confidence distribution)
**And** the guide includes: deployment instructions (update config/cluster_labels_v2.yaml, restart pipeline, validate outputs)
**And** the guide is saved as _bmad-output/analysis/run_{timestamp}/migration_guide_v1_to_v2.md

---

### Story 6.3: Validate Re-Clustering Results Before Production Deployment

As a data quality manager,
I want to validate new cluster models on historical data before deploying to production,
So that I don't introduce regressions or increase false positive rates.

**Acceptance Criteria:**

**Given** a new cluster model version (v2) has been generated
**When** I run validation testing
**Then** the system runs the new model on historical data (previous month's results)
**And** the system compares Tier 1 size (v1 vs v2) and alerts if change >20%
**And** the system validates that new Tier 1 clusters still have 0% FP rate on ground truth pairs
**And** the system runs regression tests from ground_truth/ directory with new model
**And** regression test failures are clearly reported with affected pairs
**And** the system generates a validation report recommending: APPROVE (safe to deploy) or REJECT (needs investigation)
**And** validation completes in <10 minutes

---

## Epic 7: Business Intelligence & ROI Reporting

Executive stakeholders receive comprehensive quarterly reports demonstrating ROI, efficiency gains, quality metrics, and team satisfaction.

### Story 7.1: Calculate and Display ROI Metrics Dashboard

As a CTO,
I want a dashboard showing FTE hours saved, LLM costs, and net ROI annually,
So that I can demonstrate the business value of the Pattern Discovery system.

**Acceptance Criteria:**

**Given** the pipeline has been running in production for at least one quarter
**When** I generate the ROI dashboard
**Then** the dashboard calculates: FTE hours saved (auto-merge count × 2 minutes per pair)
**And** the dashboard tracks: LLM validation costs per quarter (DeepSeek API spend)
**And** the dashboard computes: net ROI annually (FTE savings - LLM costs - implementation costs)
**And** the dashboard shows: payback period (months to recover implementation investment)
**And** the dashboard visualizes: before/after comparison (manual review burden, FP rate, auto-merge volume)
**And** the dashboard is generated as an HTML file viewable in standard browsers
**And** the dashboard includes: quarter-over-quarter trends (auto-merge volume, FP rate, efficiency)

---

### Story 7.2: Generate Quarterly Executive Summary Report

As a CTO,
I want a quarterly executive summary with volume metrics, FP rates, efficiency gains, and costs,
So that I can present results to the board and stakeholders.

**Acceptance Criteria:**

**Given** a quarter has completed with multiple production runs
**When** I generate the executive summary
**Then** the report includes: auto-merge volume (total pairs, percentage of total)
**And** the report includes: false positive rate (Tier 1: 0%, Overall: <10%)
**And** the report includes: efficiency gains (FTE hours saved, manual review reduction percentage)
**And** the report includes: operational costs (LLM validation spend, infrastructure costs)
**And** the report includes: team satisfaction metrics (data quality analyst feedback, manual review burden)
**And** the report includes: quality trends (FP rate over time, auto-merge volume over time, cluster stability)
**And** the report is exportable to PDF format with charts and visualizations
**And** charts include: volume trends (line chart), FP rate trends (line chart), ROI comparison (bar chart)

---

### Story 7.3: Track and Report Team Satisfaction Metrics

As a CTO,
I want to track team satisfaction metrics showing how the system impacts data quality analyst morale,
So that I can demonstrate the human impact beyond just efficiency numbers.

**Acceptance Criteria:**

**Given** the system has been in production for 3+ months
**When** I review team satisfaction metrics
**Then** the report includes: survey results from data quality analysts (job satisfaction, workload perception)
**And** the report includes: qualitative feedback (what they like, what frustrates them)
**And** the report includes: manual review time trends (hours per week, change over time)
**And** the report includes: error rate trends (false positives caught in review, system accuracy perception)
**And** the report includes: confidence level (do analysts trust auto-merge decisions)
**And** the report is updated quarterly with survey responses
**And** survey questions align with user journeys (Anna: "Do you trust auto-merge?", Thomas: "Has review burden decreased?", Lena: "Is the system easy to operate?")
