---
title: 'Pattern Discovery Analysis Module for Entity Resolution'
slug: 'pattern-discovery-analysis-module'
created: '2026-01-07'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack:
  - Python >=3.10 (required for modern type hints, dataclass features, and pattern matching)
  - pandas>=2.0
  - numpy
  - kmodes>=0.12.2 (NEW - categorical clustering)
  - scikit-learn>=1.3.0 (already installed - metrics)
  - openai>=1.0.0 (NEW - DeepSeek API client)
  - matplotlib>=3.7.0 (NEW - visualization)
  - seaborn>=0.12.0 (NEW - statistical plots)
  - pytest>=7.0 (already installed)
  - rapidfuzz>=3.0 (already installed - used for feature extraction)
  - python-dotenv>=1.0.0 (already installed - for .env)
files_to_modify:
  - requirements.txt (add kmodes, openai, matplotlib, seaborn)
  - .env (add DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
  - docs/businessrules.md (document pattern discovery process)
files_to_create:
  - dedupe/analysis/__init__.py
  - dedupe/analysis/pattern_discovery.py (main orchestrator)
  - dedupe/analysis/clustering.py (k-modes + validation)
  - dedupe/analysis/llm_labeling.py (DeepSeek integration)
  - dedupe/analysis/pattern_report.py (report generation)
  - dedupe/analysis/utils.py (helper functions)
  - ground_truth/calibration_set.csv
  - ground_truth/clear_duplicates.csv
  - ground_truth/clear_non_duplicates.csv
  - ground_truth/edge_cases.csv
  - ground_truth/boundary_cases.csv
  - tests/test_clustering.py
  - tests/test_llm_labeling.py
  - tests/test_business_rules.py (regression tests)
files_to_reference:
  - dedupe/scoring.py (score_pair function - 757 lines of business logic)
  - docs/businessrules.md (complete rule documentation)
  - docs/architecture.md (system architecture context)
  - docs/research/pattern-discovery-research-20260107.md (research findings)
code_patterns:
  - Dataclass pattern (frozen=True for immutability) - see MatchResult in scoring.py
  - Module-based architecture under dedupe/
  - Post-pipeline analysis (separate from production pipeline)
  - Configuration via .env file (DEDUPE_DB_*, now adding DEEPSEEK_*)
  - Type hints and docstrings for all functions
  - Error handling with try/except and safe fallbacks
test_patterns:
  - Pytest framework with descriptive test function names (test_*)
  - Parametrized tests using @pytest.mark.parametrize
  - Ground truth dataset structure for regression testing
  - Test files in tests/ directory at project root
---

# Tech-Spec: Pattern Discovery Analysis Module for Entity Resolution

**Created:** 2026-01-07

## Overview

### Problem Statement

The deduplication system produces ~170k matched pairs but lacks systematic visibility into which business rule patterns are working vs. failing. Manual review of 130k+ medium-confidence pairs (65-95% score range) is infeasible. The current rule-based system may be missing patterns that could improve precision and recall, but there's no evidence-based method to discover what additional rules would be valuable.

Without pattern discovery capabilities:
- Unknown false positive/negative rates in medium-confidence ranges
- No systematic way to identify which rule combinations are unreliable
- Cannot validate if new rule ideas would actually improve outcomes
- Continuous improvement relies on ad-hoc observation rather than data-driven analysis

### Solution

Build a **post-pipeline Pattern Discovery Analysis Module** that operates independently from the production deduplication pipeline. The module will:

1. **Extract 35 boolean rule features** from existing matched pairs (exact match, fuzzy match, DOB gate violations, etc.)
2. **Cluster pairs using k-modes algorithm** (NOT k-means) with Hamming distance, specifically designed for categorical/binary data
3. **Validate cluster count (k=15)** using Silhouette analysis to ensure meaningful pattern groups (k=15 chosen based on brainstorming session analysis estimating ~15 distinct rule pattern combinations; will validate with Silhouette analysis on k=5-30 range to confirm optimal k)
4. **Sample strategically** - 15 pairs per cluster (~225 total) for diverse coverage
5. **Use DeepSeek LLM as oracle** for binary classification (DUPLICATE/NOT_DUPLICATE) with confidence scoring
6. **Implement human-in-the-loop validation** - calibrate on 30 pairs, manually review low-confidence predictions
7. **Identify disagreement patterns** - compare LLM labels vs system scores to find rule gaps
8. **Generate actionable pattern reports** - specific recommendations for new deterministic rules
9. **Build regression test suite** - validated pairs become automated tests for future rule changes

The system creates a continuous improvement feedback loop: Pattern Discovery → Rule Insights → New Deterministic Rules → Production Deployment → Repeat Monthly/Quarterly.

**Cost:** ~$0.05-0.10 per analysis cycle (DeepSeek API only), ~$45-160 total including manual labor
**Time:** 6-10 hours total (mostly automated, ~2-3 hours human review)
**Expected Impact:** 2-5 new rules per cycle, 10-20% reduction in false positives

### Scope

**In Scope:**
- ✅ Rule feature extraction module (35 boolean columns from business rules)
- ✅ K-modes clustering implementation with Hamming distance
- ✅ Silhouette analysis for k validation (test k=5 to k=30)
- ✅ Stratified sampling strategy (15 pairs per cluster = ~225 total)
- ✅ DeepSeek LLM integration with few-shot prompting and confidence scoring
- ✅ Human-in-the-loop calibration workflow (30-pair validation set)
- ✅ Confidence-based filtering (auto-accept high confidence, review low confidence)
- ✅ Pattern analysis comparing LLM labels vs system scores
- ✅ Pattern report generation (markdown format with visualizations)
- ✅ Regression test framework using pytest for validated pairs
- ✅ Ground truth dataset structure (clear duplicates, clear non-duplicates, edge cases, boundary cases)
- ✅ All 4 implementation phases:
  - Phase 1: Foundation (clustering setup)
  - Phase 2: Calibration (LLM validation)
  - Phase 3: Full Analysis (225 pairs)
  - Phase 4: Rule Implementation (feedback loop)

**Out of Scope:**
- ❌ Real-time/inline pattern discovery (post-pipeline batch processing only)
- ❌ Multi-LLM ensemble (single DeepSeek model + human validation is more cost-effective)
- ❌ Automated rule generation (requires human approval and validation)
- ❌ Production pipeline modifications (analysis is separate, does not impact main pipeline)
- ❌ Re-processing of source data (works with existing `modular_results.csv`)
- ❌ Alternative clustering algorithms beyond k-modes (DBSCAN, hierarchical, etc. - future work)
- ❌ Association rule mining (mentioned in research as advanced technique - future enhancement)

## Context for Development

### Codebase Patterns

**Existing Architecture:**
- Main pipeline: `dedupe/pipeline.py` orchestrates preprocessing → blocking → scoring → output
- Rule-based scoring: `dedupe/scoring.py` with `MatchResult` dataclass pattern (frozen=True, immutable)
- Business rules: 757 lines of scoring logic with gates, thresholds, and penalties
- Business rules documented: `docs/businessrules.md` (gates, match types, scoring logic)
- Output format: CSV with columns `i, j, score, name_score, addr_score, reason, is_swapped, [record fields]`
- Testing: 12 existing test files in `tests/` using pytest framework
- Configuration: `.env` file with `DEDUPE_DB_*` variables using python-dotenv

**Current Results:**
- ~170k matched pairs in `modular_results.csv`
- ~40k high confidence (≥95%) - likely true matches
- ~130k medium confidence (65-95%) - need analysis
- ~1k low confidence (<65%) - likely non-matches

**Business Rules Identified (35 Boolean Features):**

From `dedupe/scoring.py` analysis, these rule evaluations will become boolean columns (0/1 integer encoding):

*Match Type Features (16):*
1. `exact_normal` - First==First, Last==Last
2. `exact_swapped` - First==Last, Last==First
3. `exact_normal_different_gender` - Exact match but different genders
4. `exact_swapped_different_gender` - Exact swapped but different genders
5. `fuzzy_normal` - Fuzzy match (≥threshold)
6. `fuzzy_swapped` - Fuzzy match swapped
7. `fuzzy_normal_different_gender`
8. `fuzzy_swapped_different_gender`
9. `address_assisted_normal` - Borderline name + strong address
10. `address_assisted_swapped`
11. `address_assisted_normal_different_gender`
12. `address_assisted_swapped_different_gender`
13. `phonetic_assisted_normal` - Cologne phonetics match
14. `phonetic_assisted_swapped`
15. `phonetic_assisted_normal_different_gender`
16. `phonetic_assisted_swapped_different_gender`

*Hard Gate Features (4):*
17. `gate_dob_conflict` - Both have DOB, different (lines 234-238)
18. `gate_yob_conflict` - Both have YOB, different (lines 241-246)
19. `gate_house_conflict` - Same PLZ+street, different house numbers (lines 375-377, 699-701)
20. `gate_zweitname_conflict` - Name2 mismatch (lines 284-287)

*Data Quality Features (6):*
21. `both_dob_missing` - Neither has DOB
22. `one_dob_missing` - Only one has DOB
23. `both_have_exact_dob` - Both have matching DOB
24. `yob_only_match` - Have YOB but not exact DOB
25. `both_yob_missing` - Neither has YOB
26. `one_yob_missing` - Only one has YOB

*Similarity Tier Features (9+):*
27. `name_similarity_high` - ≥90%
28. `name_similarity_medium` - 75-90%
29. `name_similarity_low` - <75%
30. `first_similarity_high` - ≥75%
31. `last_similarity_high` - ≥80%
32. `address_ratio_strong` - ≥0.9
33. `address_ratio_moderate` - 0.5-0.9
34. `address_ratio_weak` - <0.5
35. `different_genders_same_address` - Gender mismatch at same building

**Design Decisions from Research:**
- **CRITICAL:** Must use k-modes (NOT k-means) - research proves k-means is inappropriate for boolean features
- **Distance metric:** Hamming distance (counts mismatches in binary features)
- **Cluster validation:** Silhouette score with metric='hamming'
- **LLM strategy:** Single model + human validation (more cost-effective than ensemble)
- **Architecture:** Post-pipeline (no impact on production performance)

### Files to Reference

| File | Purpose | Key Insights |
| ---- | ------- | ------------ |
| `dedupe/scoring.py` | Understand rule evaluation logic to extract boolean features | 757 lines, MatchResult dataclass (frozen=True), score_pair() function with 26+ distinct rule checks |
| `docs/businessrules.md` | Document all business rules (gates, match types, scoring) | Hard gates (DOB/YOB/house/zweitname), soft gates (gender), match types with confidence ranges |
| `docs/research/pattern-discovery-research-20260107.md` | Complete research findings with algorithms, metrics, best practices | K-modes algorithm details, Silhouette validation, DeepSeek accuracy (85%+), cost analysis ($0.05 per cycle) |
| `_bmad-output/analysis/brainstorming-session-20260107.md` | Original design concept (note: k-means must be changed to k-modes) | Initial k=15 choice, 225 samples strategy, binary classification approach |
| `docs/architecture.md` | Overall system architecture and extension points | Pipeline stages, MatchResult pattern, dual scoring modes, extension points |
| `CLAUDE.md` | Change documentation requirements (story files required) | Every change needs docs/stories/YYYYMMddHHmmss-topic.md file |
| `requirements.txt` | Existing dependencies | Already has pandas, numpy, scikit-learn, pytest, rapidfuzz, python-dotenv |
| `.env.example` | Configuration pattern | DEDUPE_DB_* variables, follow same pattern for DEEPSEEK_* |
| `tests/test_dedupe_business_rules.py` | Test pattern examples | Pytest framework, parametrized tests, descriptive function names |

### Technical Decisions

**1. Clustering Algorithm: K-modes (NOT K-means)**
- **Rationale:** Research finding - k-means with Euclidean distance is meaningless for boolean/categorical data
- **Implementation:** Use `kmodes` library (scikit-learn-like API)
- **Parameters:**
  - `n_clusters=15` (validate with Silhouette analysis)
  - `init='Huang'` (Huang initialization method for k-modes)
  - `n_init=10` (multiple runs to avoid local optima)
  - `n_jobs=-1` (parallel processing using all CPU cores)
  - `random_state=42` (reproducibility)
- **Validation:** Silhouette analysis with `metric='hamming'` to validate k=15
- **Expected Performance:** <10 minutes for 170k records
- **Reference:** [IBM: Clustering binary data with K-Means (should be avoided)](https://www.ibm.com/support/pages/clustering-binary-data-k-means-should-be-avoided)

**2. LLM Provider: DeepSeek**
- **Rationale:** 85%+ accuracy, 224x-4500x cheaper than manual annotation ($0.04-0.10 for 225 pairs)
- **API:** OpenAI-compatible client pointing to `https://api.deepseek.com`
- **Model:** `deepseek-chat`
- **Configuration:** Via `.env` file with:
  - `DEEPSEEK_API_KEY=sk-your-key-here`
  - `DEEPSEEK_BASE_URL=https://api.deepseek.com`
  - `DEEPSEEK_MODEL=deepseek-chat`
- **Parameters:**
  - `temperature=0.0` (deterministic for consistency)
  - Response format: JSON

**3. Prompting Strategy: Few-shot Binary Classification**
- **Format:** 2-4 examples of DUPLICATE and NOT_DUPLICATE pairs
- **Examples include:** Swiss-specific patterns (umlauts, compound names, address formats)
- **Output:** JSON with `{"label": "DUPLICATE"|"NOT_DUPLICATE", "confidence": 0.0-1.0, "reasoning": "..."}`
- **Threshold:** Auto-accept confidence ≥0.85, manual review <0.85
- **Expected:** ~70% auto-accepted (≤30% requiring review)

**4. Module Structure: Separate Analysis Package**
- **Location:** `dedupe/analysis/` (new package, follows existing pattern)
- **Rationale:** Keeps analysis code separate from production pipeline, modular design
- **Files:**
  - `__init__.py` - Package exports
  - `pattern_discovery.py` - Main orchestrator (Phase 1-4 coordination)
  - `clustering.py` - K-modes clustering + Silhouette validation
  - `llm_labeling.py` - DeepSeek integration with confidence filtering
  - `pattern_report.py` - Markdown report generation with visualizations
  - `utils.py` - Rule feature extraction, helper functions
- **Pattern:** Follow existing `dedupe/` module structure (type hints, docstrings, error handling)

**5. Rule Feature Extraction Strategy:**
- **Source:** Parse `modular_results.csv` output from main pipeline
- **Method:** Re-evaluate `score_pair()` logic to extract boolean flags
- **Features:** 35+ boolean columns (26 from scoring.py + derived features)
- **Datatype:** Convert boolean to int (0/1) for k-modes input
- **Storage:** Add as new columns to `clustered_results.csv`

**6. Output Organization:**
- **Location:** `{output_folder}/analysis/` → `_bmad-output/analysis/`
- **Structure:** Each analysis run creates timestamped subdirectory: `_bmad-output/analysis/run_YYYYMMDD_HHMMSS/`
- **Files (per run):**
  - `clustered_results.csv` - All 170k pairs with cluster assignments + rule features
  - `cluster_samples.csv` - 225 sampled pairs (15 per cluster)
  - `llm_labeled.csv` - LLM labels + confidence + reasoning
  - `pattern_report.md` - Analysis findings and recommendations
  - `cluster_validation.png` - Silhouette + elbow plots (matplotlib)
- **Collision Handling:**
  - Timestamp precision: Microseconds (`YYYYMMDD_HHMMSS_ffffff`) if run twice in same second
  - If subdirectory already exists (rare): Append `_2`, `_3`, etc. suffix
  - Symlink: Create `_bmad-output/analysis/latest` → most recent run for easy access
  - Cleanup: Keep last 10 runs, auto-archive older runs to `_bmad-output/analysis/archive/` (optional)

**7. Ground Truth Structure:**
- **Location:** `ground_truth/` directory at project root
- **CSV Format:** Same columns as `modular_results.csv` + `manual_label` + `labeled_by` + `labeled_date` columns
- **Files:**
  - `calibration_set.csv` - 30 manually labeled pairs (Phase 2)
  - `clear_duplicates.csv` - High-confidence matches (70-90 pairs, Phase 3)
  - `clear_non_duplicates.csv` - High-confidence non-matches (70-90 pairs, Phase 3)
  - `edge_cases.csv` - Borderline cases (45-65 pairs, Phase 3)
  - `boundary_cases.csv` - At-threshold cases (20-25 pairs, Phase 3)
- **Usage:** Regression tests via pytest parametrize
- **Versioning & Rollback:**
  - Every ground truth update creates backup in `ground_truth_archive/YYYYMMDD_HHMMSS/`
  - Archive preserves exact state before modification for audit trail
  - Rollback: Copy files from archive back to `ground_truth/` if labeling error discovered
  - Corruption detection: Compare row counts before/after updates, log discrepancies
  - Git tracking: Commit ground truth changes with descriptive messages referencing analysis cycle date

**8. Error Handling & Validation:**
- **Input validation:** Check `modular_results.csv` exists and has expected columns
- **API errors:** Retry logic for DeepSeek API (3 retries with exponential backoff)
- **Data quality:** Warn if missing critical fields (DOB, address, etc.)
- **Cluster validation:**
  - Fail if Silhouette score <0.3 (poor clustering quality, not usable)
  - Warn if 0.3 ≤ score < 0.5 (acceptable but suboptimal, proceed with caution)
  - Target score ≥0.5 (well-defined clusters, optimal quality)
- **Output validation:** Verify all expected files generated

**9. Concurrent Execution Safety:**
- **File Locking:** Use file-based lock (`_bmad-output/analysis/.lock`) to prevent concurrent runs
  - Acquire lock at start of analysis, release at end
  - If lock exists and is <4 hours old: Fail with "Analysis already running" message
  - If lock exists and is >4 hours old: Warn "Stale lock detected", prompt user to force-override
- **Ground Truth Updates:** Use atomic file operations (write to temp, then rename) to prevent corruption
- **Output Collisions:** Timestamp-based folders (`YYYYMMDD_HHMMSS`) ensure unique output per run
- **Recommendation:** Do NOT run pattern discovery concurrently; sequential execution recommended
- **random_state=42:** Ensures reproducibility but does NOT provide thread safety

## Implementation Plan

### Tasks

Implementation is organized into 4 phases with clear dependencies. Complete phases sequentially.

#### **Phase 1: Foundation (Clustering Infrastructure)**

**Goal:** Set up k-modes clustering with validation, confirm algorithm works correctly

- [ ] Task 1.1: Add new dependencies to requirements.txt
  - File: `requirements.txt`
  - Action: Add lines after existing ML dependencies:
    ```
    # Pattern Discovery Analysis Module
    kmodes>=0.12.2          # K-modes clustering for categorical data
    openai>=1.0.0           # DeepSeek API (OpenAI-compatible)
    matplotlib>=3.7.0       # Visualization
    seaborn>=0.12.0         # Statistical visualization
    ```
  - Dependency Conflict Check:
    - Verify matplotlib 3.7+ is compatible with current numpy version (requires numpy>=1.20)
    - Verify seaborn 0.12+ is compatible with matplotlib 3.7+ (yes, seaborn 0.12 requires matplotlib 3.1+)
    - Verify openai 1.0+ doesn't conflict with existing packages (check for shared dependencies like requests, httpx)
    - Test: Run `pip install -r requirements.txt` in clean venv, verify no conflicts
    - If conflicts arise: Use `pip-compile` or specify compatible version ranges
  - Notes: Group with ML dependencies section; test installation before committing

- [ ] Task 1.2: Create dedupe/analysis package structure
  - Files:
    - `dedupe/analysis/__init__.py`
  - Action: Create empty `__init__.py` file to make dedupe/analysis a Python package
  - Notes: Will add exports later as modules are created

- [ ] Task 1.3: Implement rule feature extraction utilities
  - File: `dedupe/analysis/utils.py`
  - Action: Create module with these functions:
    - `extract_rule_features(pair_row, cols) -> dict[str, bool]` - Extract 35+ boolean features from a pair
      - Parse `reason` field to identify match type
      - Reconstruct DOB/YOB checks from pair data
      - Calculate name/address similarity tiers
      - Return dict of feature_name: boolean_value
    - `load_modular_results(filepath: str) -> pd.DataFrame` - Load and validate modular_results.csv
      - Check file exists
      - Validate required columns present (i, j, score, name_score, addr_score, reason, etc.)
      - Check file modification timestamp (warn if >7 days old - may be stale)
      - Validate data integrity (no null values in critical columns, score ranges 0-100)
      - Return DataFrame
    - `convert_features_to_binary_matrix(df: pd.DataFrame) -> np.ndarray` - Convert feature dict to 0/1 numpy array
      - Extract features for all pairs
      - Convert boolean to int
      - Return (n_pairs, n_features) array
  - Notes: Reference `dedupe/scoring.py` lines 234-756 for rule logic, use same threshold values

- [ ] Task 1.4: Implement k-modes clustering module
  - File: `dedupe/analysis/clustering.py`
  - Action: Create module with these functions and classes:
    - `perform_kmodes_clustering(X: np.ndarray, n_clusters: int = 15, random_state: int = 42) -> tuple` - Run k-modes
      - Use kmodes.KModes with init='Huang', n_init=10, n_jobs=-1
      - Return (cluster_labels, cluster_centroids, cost)
    - `validate_k_silhouette(X: np.ndarray, k_range: range = range(5, 31)) -> dict` - Test multiple k values
      - For each k, run k-modes and calculate Silhouette score with metric='hamming'
      - Return dict with k: silhouette_score, k: cost
    - `plot_cluster_validation(silhouette_scores: dict, costs: dict, current_k: int = 15, output_path: str = None)` - Generate validation plots
      - Create 2-panel figure (Silhouette + Elbow)
      - Mark current k=15 with vertical line
      - Save to output_path if provided
      - **Visualization Standards:**
        - Format: PNG (primary), also save as SVG for scalability
        - DPI: 300 (publication quality)
        - Figure size: 12×6 inches (accommodates 2 panels side-by-side)
        - Color palette: Use colorblind-safe palette (matplotlib 'tab10' or seaborn 'colorblind')
        - Font sizes: Title 14pt, axis labels 12pt, tick labels 10pt
        - Grid: Light gray gridlines for readability
        - Legend: Position auto (best), font size 10pt
    - `get_cluster_profiles(centroids: np.ndarray, feature_names: list[str]) -> pd.DataFrame` - Interpret cluster modes
      - Convert centroids to DataFrame with feature names
      - Return readable cluster profiles
  - Notes: Use type hints, add docstrings with parameter descriptions

- [ ] Task 1.5: Create unit tests for clustering
  - File: `tests/test_clustering.py`
  - Action: Write pytest test functions:
    - `test_kmodes_on_sample_data()` - Verify k-modes runs without errors on small synthetic dataset
    - `test_silhouette_calculation()` - Verify Silhouette score calculated correctly with Hamming distance
    - `test_cluster_profile_interpretation()` - Verify centroids converted to readable format
  - Notes: Use small test datasets (100 rows, 10 features) for speed

- [ ] Task 1.6: Run Phase 1 end-to-end test
  - File: `dedupe/analysis/pattern_discovery.py` (create initial version)
  - Action: Create Phase 1 runner script:
    - Load modular_results.csv
    - Extract rule features for all 170k pairs
    - Run k-modes with n_clusters=15
    - Run Silhouette validation for k=5 to k=30
    - Generate cluster validation plots
    - Save clustered_results.csv with cluster assignments
    - Print cluster sizes and Silhouette score
  - Acceptance: Clustering completes in <10 minutes, Silhouette score >0.3, cluster validation plots generated

#### **Phase 2: LLM Calibration**

**Goal:** Integrate DeepSeek API, calibrate confidence thresholds with 30-pair validation set

- [ ] Task 2.1a: Create .env.example template file
  - File: `.env.example`
  - Action: Add DeepSeek configuration template (safe to commit):
    ```
    # DeepSeek API Configuration for Pattern Discovery
    # Copy this file to .env and fill in your actual API key
    # NEVER commit .env to git - it should already be in .gitignore
    DEEPSEEK_API_KEY=sk-your-key-here-replace-with-actual-key
    DEEPSEEK_BASE_URL=https://api.deepseek.com
    DEEPSEEK_MODEL=deepseek-chat
    ```
  - Notes: This template is safe to commit to version control

- [ ] Task 2.1b: Add DeepSeek configuration to .env (user action)
  - File: `.env`
  - Action: User copies .env.example to .env and fills in actual API key
  - Validation: Verify .env is listed in .gitignore (prevent accidental key exposure)
  - Security:
    - API keys should be rotated quarterly
    - Use separate API keys for dev/staging/production
    - Monitor API usage for unexpected spikes
  - Notes: CRITICAL - .env must NEVER be committed to git

- [ ] Task 2.2: Implement DeepSeek LLM integration
  - File: `dedupe/analysis/llm_labeling.py`
  - Action: Create module with these functions:
    - `DeepSeekClient` class:
      - `__init__(self, api_key: str, base_url: str, model: str)` - Initialize OpenAI client
      - `label_pair(self, pair_data: dict, few_shot_examples: list = None) -> dict` - Get LLM label for single pair
        - Build few-shot prompt with 2-4 examples (Swiss-specific patterns)
        - Call DeepSeek API with temperature=0.0
        - Parse JSON response: {"label": "DUPLICATE"|"NOT_DUPLICATE", "confidence": float, "reasoning": str}
        - Implement retry logic with circuit breaker:
          - Max 3 retry attempts with exponential backoff (1s, 2s, 4s)
          - Max total delay per request: 10 seconds
          - Circuit breaker: After 5 consecutive failures, pause API calls for 60 seconds
          - Cost ceiling: Track API costs, fail if exceeding $5.00 per run (safety limit)
          - Log all retry attempts with timestamps and error messages
        - Return result dict or raise exception if all retries exhausted
      - `label_batch(self, pairs: pd.DataFrame, few_shot_examples: list = None, confidence_threshold: float = 0.85) -> tuple` - Label multiple pairs
        - Call label_pair for each pair
        - Track high-confidence vs low-confidence
        - Return (labeled_df, low_confidence_indices)
    - `get_default_few_shot_examples() -> list[dict]` - Return 2-4 calibrated Swiss examples
  - Notes: Handle API errors gracefully, log retry attempts

- [ ] Task 2.3: Create calibration workflow
  - File: `dedupe/analysis/pattern_discovery.py` (add Phase 2 function)
  - Action: Implement `run_calibration_phase(clustered_results_path: str, output_dir: str)`:
    - Stratified sample 30 pairs across clusters (2 per cluster)
    - Display pairs to user for manual labeling (print to console with input prompts)
    - Interactive input handling:
      - Accept inputs: "D" (duplicate), "N" (not duplicate), "S" (skip), "Q" (save and quit)
      - Validate input (reject invalid entries, prompt again)
      - Save progress after every 5 labels (auto-save to temp file)
      - Support resume: If partial calibration_set.csv exists, offer to continue where left off
      - Timeout: None (manual labeling can take as long as needed, save/resume available)
    - Save manual labels to `ground_truth/calibration_set.csv`
    - Run DeepSeek on same 30 pairs
    - Compare LLM vs manual labels
    - Calculate accuracy by confidence tier (>0.9, 0.7-0.9, <0.7)
    - Print calibration report with recommended threshold
    - Return suggested confidence_threshold
  - Notes: Interactive - requires user input, supports save/resume for long sessions

- [ ] Task 2.4: Create unit tests for LLM integration
  - File: `tests/test_llm_labeling.py`
  - Action: Write pytest test functions:
    - `test_prompt_formatting()` - Verify few-shot prompt constructed correctly
    - `test_json_parsing()` - Verify LLM response parsed correctly
    - `test_retry_logic()` (mock API failures) - Verify retries work
    - `test_confidence_filtering()` - Verify high/low confidence split works
  - Notes: Mock DeepSeek API calls, don't hit real API in tests

#### **Phase 3: Full Analysis (225 Pairs)**

**Goal:** Run complete pattern discovery on 225 sampled pairs, generate pattern report

- [ ] Task 3.1: Implement stratified sampling
  - File: `dedupe/analysis/utils.py` (add function)
  - Action: Add `stratified_sample_from_clusters(df: pd.DataFrame, cluster_column: str, samples_per_cluster: int = 15, random_state: int = 42) -> pd.DataFrame`:
    - Sample N pairs from each cluster
    - Handle edge cases:
      - If cluster has >=15 pairs: Sample exactly 15 pairs randomly
      - If cluster has <15 pairs: Sample ALL pairs from that cluster (don't skip small clusters)
      - If cluster has 0 pairs: Log warning, skip cluster
      - Track total samples per cluster in metadata for reporting
    - Return sampled DataFrame with cluster_size metadata column
  - Notes: Graceful handling = include all available pairs from small clusters, never skip

- [ ] Task 3.2: Implement pattern analysis
  - File: `dedupe/analysis/pattern_report.py`
  - Action: Create module with these functions:
    - `analyze_disagreements(llm_labeled: pd.DataFrame, system_threshold: float = 75.0) -> pd.DataFrame` - Find LLM vs system disagreements
      - LLM says DUPLICATE but system score <threshold
      - LLM says NOT_DUPLICATE but system score ≥threshold
      - Group by cluster
      - Return disagreement summary
    - `identify_rule_patterns(llm_labeled: pd.DataFrame, rule_features: pd.DataFrame) -> dict` - Find patterns in disagree cases
      - For high-disagreement clusters, identify common rule combinations
      - Calculate correlation between rules and LLM disagreement
      - Return pattern insights dict
    - `generate_pattern_report(analysis_results: dict, output_path: str)` - Create markdown report
      - Executive summary with key findings
      - Cluster-by-cluster analysis
      - Top 5 recommended rule improvements
      - Visualizations (cluster sizes, disagreement rates, rule correlations)
      - Save to output_path
  - Notes: Use markdown tables, embed matplotlib plots as PNG

- [ ] Task 3.3: Implement Phase 3 runner
  - File: `dedupe/analysis/pattern_discovery.py` (add Phase 3 function)
  - Action: Implement `run_full_analysis_phase(clustered_results_path: str, calibration_threshold: float, output_dir: str)`:
    - Load clustered results
    - Stratified sample 225 pairs (15 per cluster)
    - Save to `{output_dir}/cluster_samples.csv`
    - Run DeepSeek labeling on all 225 pairs
    - Flag low-confidence pairs for manual review
    - Print list of low-confidence pairs for user review
    - User reviews and corrects labels (interactive)
    - Spot-check 15-20 high-confidence pairs (random sample, user validates)
    - Save final labels to `{output_dir}/llm_labeled.csv`
    - Run pattern analysis
    - Generate pattern report
    - Categorize validated pairs into ground truth files:
      - clear_duplicates.csv
      - clear_non_duplicates.csv
      - edge_cases.csv
      - boundary_cases.csv
    - Print summary: pairs labeled, disagreement rate, top patterns
  - Notes: Interactive phase requiring human input

- [ ] Task 3.4: Create ground truth directory structure
  - Files:
    - `ground_truth/.gitkeep` (or README.md)
  - Action: Create ground_truth/ directory, add .gitkeep or README explaining structure
  - Notes: CSV files will be created during Phase 2 and 3 execution

#### **Phase 4: Regression Testing & Documentation**

**Goal:** Build automated regression tests, document pattern discovery process

- [ ] Task 4.1: Implement regression test framework
  - File: `tests/test_business_rules.py`
  - Action: Create pytest test functions using ground truth data:
    - `test_clear_duplicates(pair)` - Parametrized test for clear_duplicates.csv
      - Load pair, run score_pair()
      - Assert result.score >= 95 (high confidence)
    - `test_clear_non_duplicates(pair)` - Parametrized test for clear_non_duplicates.csv
      - Load pair, run score_pair()
      - Assert result.score < 75 (low confidence) or result is None
    - `test_edge_cases(pair)` - Parametrized test for edge_cases.csv
      - Load pair, run score_pair()
      - Assert 65 <= result.score <= 95 (in review queue)
    - `test_boundary_cases(pair)` - Parametrized test for boundary_cases.csv
      - Load pair, run score_pair()
      - Assert score near threshold (within ±5 points)
  - Notes: Use `@pytest.mark.parametrize` to load pairs from CSV, tests run automatically on every code change
  - Ground Truth Update Policy (when tests fail):
    - **ONLY update ground truth if**: Business requirements changed (e.g., new threshold approved by stakeholders)
    - **Fix code if**: Test failure indicates unintended regression or bug
    - **Process**: Document reason for ground truth updates in git commit message with stakeholder approval reference
    - **Version**: Keep old ground truth as ground_truth_archive/YYYYMMDD/ for audit trail

- [ ] Task 4.2: Document pattern discovery process
  - File: `docs/businessrules.md`
  - Action: Add new section "Pattern Discovery Analysis" at end of document:
    - Overview of pattern discovery module
    - How to run analysis (command examples)
    - How to interpret pattern reports
    - How rule improvements are identified
    - Frequency recommendations (monthly/quarterly)
  - Notes: Keep concise, link to research doc for details

- [ ] Task 4.3: Create story documentation file
  - File: `docs/stories/YYYYMMddHHmmss-pattern-discovery-analysis-module.md` (use current UTC timestamp)
  - Action: Create change documentation per CLAUDE.md requirements:
    - Summary: Pattern discovery analysis module implementation
    - Context/Problem: Need systematic way to discover rule gaps
    - What Changed: List all new files created, dependencies added
    - How to Test: Step-by-step instructions to run each phase
    - Risk/Rollback Notes: Post-pipeline module, no impact on production; can be disabled by not running
  - Notes: Required per CLAUDE.md, include in same commit as code

- [ ] Task 4.4: Create main CLI entry point
  - File: `dedupe/analysis/pattern_discovery.py` (add main block)
  - Action: Add `if __name__ == '__main__':` block with argparse CLI:
    - Command: `python -m dedupe.analysis.pattern_discovery --phase {1|2|3|4|all}`
    - Arguments with validation:
      - `--input` - Path to modular_results.csv (default: modular_results.csv)
        - Validate: File must exist and be readable
      - `--output-dir` - Output directory (default: _bmad-output/analysis)
        - Validate: Directory must exist or be creatable
      - `--phase` - Which phase to run (choices: 1, 2, 3, 4, all)
        - Validate: Must be one of the allowed choices
      - `--clusters` - Number of clusters (default: 15)
        - Validate: Must be integer >=5 and <=50 (reasonable range)
      - `--confidence-threshold` - LLM confidence threshold (default: 0.85)
        - Validate: Must be float between 0.0 and 1.0
    - Error handling: Print helpful error messages for invalid arguments, don't crash silently
    - Print clear instructions for each phase
  - Notes: Make it easy to run from command line, fail fast with clear errors

- [ ] Task 4.5: Implement logging and progress tracking
  - File: `dedupe/analysis/pattern_discovery.py` (add to all modules)
  - Action: Add comprehensive logging using Python logging module:
    - **Logging Levels:**
      - DEBUG: Feature extraction details, API request/response bodies
      - INFO: Phase transitions, progress indicators (10%, 20%, etc.), cluster assignments
      - WARNING: Data freshness issues, stale locks, low Silhouette scores (0.3-0.5)
      - ERROR: API failures, file not found, invalid data, clustering failures
      - CRITICAL: Cost ceiling exceeded, fatal validation errors
    - **Log Format:** `[%(asctime)s] %(levelname)s - %(name)s:%(lineno)d - %(message)s`
    - **Output:** Both console (INFO+) and file (`_bmad-output/analysis/pattern_discovery.log`)
    - **Progress Tracking:**
      - Clustering: Log progress every 10% of data processed
      - LLM labeling: Log after each batch of 25 pairs
      - Phase completion: Log summary statistics (time elapsed, records processed, errors encountered)
    - **Metrics to Log:**
      - Runtime per phase (seconds)
      - API call count and total cost ($)
      - Pairs processed, pairs failed validation
      - Silhouette scores for each k tested
      - Manual review count (expected vs actual)
  - Notes: Enable developers to monitor long-running processes and diagnose issues

### Acceptance Criteria

**Phase 1: Foundation**

- [ ] AC 1.1: Given requirements.txt is updated, when `pip install -r requirements.txt` is run, then kmodes, openai, matplotlib, seaborn are installed without errors
- [ ] AC 1.2: Given modular_results.csv exists, when rule features are extracted, then 35 boolean feature columns are created with correct values matching scoring.py logic
- [ ] AC 1.2b: Given a random sample of 100 pairs, when extracted features are compared with live score_pair() evaluation, then feature values match exactly (100% accuracy) for all 35 features
- [ ] AC 1.3: Given 170k pairs with boolean features, when k-modes clustering runs, then clustering completes in <10 minutes and produces 15 cluster assignments
- [ ] AC 1.4: Given k-modes clustering with k=15, when Silhouette score is calculated with metric='hamming', then score is ≥0.3 (minimum acceptable clustering quality; ≥0.5 is optimal)
- [ ] AC 1.5: Given Silhouette validation runs for k=5 to k=30, when cluster validation plots are generated, then both Silhouette and Elbow plots are saved as PNG
- [ ] AC 1.6: Given clustering completes, when cluster profiles are generated, then centroids show interpretable boolean patterns for each cluster
- [ ] AC 1.7: Given Phase 1 tests run, when `pytest tests/test_clustering.py` executes, then all tests pass

**Phase 2: LLM Calibration**

- [ ] AC 2.1: Given .env file has DEEPSEEK_API_KEY, when DeepSeekClient initializes, then client connects successfully without errors
- [ ] AC 2.2: Given a pair is sent to DeepSeek, when API call succeeds, then response contains valid JSON with label, confidence (0.0-1.0), and reasoning
- [ ] AC 2.3: Given API call fails, when retry logic triggers, then system retries up to 3 times with exponential backoff before failing
- [ ] AC 2.4: Given 30 pairs are manually labeled, when DeepSeek labels the same pairs, then accuracy is calculated by confidence tier and printed to console
- [ ] AC 2.5: Given calibration completes, when confidence threshold is recommended, then threshold is based on actual accuracy data (e.g., 0.85 if >90% accurate at that level)
- [ ] AC 2.6: Given calibration_set.csv is created, when file is inspected, then it contains all 30 pairs with manual_label column
- [ ] AC 2.7: Given Phase 2 tests run, when `pytest tests/test_llm_labeling.py` executes, then all tests pass

**Phase 3: Full Analysis**

- [ ] AC 3.1: Given clustered results exist, when stratified sampling runs, then exactly 225 pairs are sampled (15 per cluster, or all if cluster <15)
- [ ] AC 3.2: Given 225 pairs are sent to DeepSeek, when labeling completes, then all pairs have LLM labels with confidence scores
- [ ] AC 3.3: Given confidence threshold is 0.85, when low-confidence pairs are identified, then ≤30% of pairs (≤68 pairs) require manual review
- [ ] AC 3.3b: Given exactly 68 pairs with confidence <0.85 (30% boundary), when threshold logic runs, then all 68 are flagged for manual review
- [ ] AC 3.3c: Given 69 pairs with confidence <0.85 (31%), when analysis runs, then system warns that manual review exceeds 30% target and suggests adjusting threshold
- [ ] AC 3.4: Given manual review is complete, when llm_labeled.csv is saved, then file contains all 225 pairs with final validated labels
- [ ] AC 3.5: Given LLM labels vs system scores, when disagreement analysis runs, then high-disagreement clusters are identified and ranked
- [ ] AC 3.6: Given pattern analysis completes, when pattern_report.md is generated, then report includes:
  - Executive summary with 2-5 recommended rule improvements
  - Cluster-by-cluster analysis table
  - Disagreement rate visualizations
  - Top rule pattern correlations
- [ ] AC 3.7: Given validated pairs are categorized, when ground truth files are created, then pairs are split into 4 categories (clear dup, clear non-dup, edge, boundary) with reasonable distributions

**Phase 4: Regression Testing & Documentation**

- [ ] AC 4.1: Given ground truth files exist, when regression tests run, then pytest loads pairs and validates scoring behavior
- [ ] AC 4.2: Given clear_duplicates.csv contains 70-90 pairs, when tests run on each pair, then all pairs score ≥95% (no regressions)
- [ ] AC 4.3: Given clear_non_duplicates.csv contains 70-90 pairs, when tests run on each pair, then all pairs score <75% or return None (no false positives)
- [ ] AC 4.4: Given businessrules.md is updated, when file is reviewed, then Pattern Discovery Analysis section explains how to run analysis and interpret results
- [ ] AC 4.5: Given story file is created, when docs/stories/ is checked, then YYYYMMddHHmmss-pattern-discovery-analysis-module.md exists with all required sections
- [ ] AC 4.6: Given CLI entry point exists, when `python -m dedupe.analysis.pattern_discovery --help` runs, then usage instructions are displayed
- [ ] AC 4.7: Given --phase all is used, when CLI runs end-to-end, then all 4 phases execute in sequence with clear progress indicators

**Overall System Integration**

- [ ] AC 5.1: Given all phases complete, when pattern discovery runs end-to-end, then total execution time is <4 hours (excluding manual review time)
- [ ] AC 5.2: Given pattern report identifies 2-5 rule improvements, when recommendations are reviewed by domain expert, then recommendations are actionable and specific
- [ ] AC 5.3: Given analysis cost is tracked, when DeepSeek API usage is calculated, then total cost is <$1.00 per 225-pair analysis cycle
- [ ] AC 5.4: Given regression tests are in place, when scoring.py is modified in future, then tests catch unintended changes to validated pairs

## Additional Context

### Dependencies

**New Dependencies to Add to `requirements.txt`:**
```python
# Pattern Discovery Analysis Module
kmodes>=0.12.2          # K-modes clustering for categorical data
openai>=1.0.0           # DeepSeek API (OpenAI-compatible)
matplotlib>=3.7.0       # Visualization
seaborn>=0.12.0         # Statistical visualization
```

**Existing Dependencies (already in requirements):**
- `pandas>=2.0` - Data manipulation
- `numpy` - Numerical operations
- `scikit-learn>=1.3.0` - Silhouette score calculation
- `pytest>=7.0` - Testing framework
- `rapidfuzz>=3.0` - String similarity (used in rule feature extraction)
- `python-dotenv>=1.0.0` - Environment variable loading

**External Service Dependencies:**
- **DeepSeek API** - Requires API key, ~$0.05 per 225-pair analysis
- **Modular results CSV** - Produced by main deduplication pipeline (must exist before running analysis)

**Python Version:** 3.x (compatible with existing project)

### Testing Strategy

**Unit Tests (tests/):**
- `test_clustering.py` - K-modes implementation, Silhouette calculation, cluster profiling
  - Mock clustering with small datasets (100 rows, 10 features)
  - Verify Hamming distance metric used correctly
  - Test edge cases (k=1, k>n_samples)
- `test_llm_labeling.py` - DeepSeek API integration, prompt formatting, retry logic
  - Mock API calls (don't hit real DeepSeek in tests)
  - Verify JSON parsing handles malformed responses
  - Test retry exponential backoff timing
  - Test confidence threshold filtering

**Regression Tests (tests/):**
- `test_business_rules.py` - Parametrized tests using ground truth validated pairs
  - Load pairs from `ground_truth/*.csv`
  - Run `score_pair()` for each pair
  - Assert scoring matches expected behavior (no regressions)
  - Categories: clear_duplicates (≥95%), clear_non_duplicates (<75%), edge_cases (65-95%), boundary_cases (near threshold)

**Integration Tests:**
- **Phase 1 End-to-End:** Run clustering on full 170k pairs, verify outputs
- **Phase 2 Calibration:** Run on 30-pair sample (mocked DeepSeek), verify accuracy calculation
- **Phase 3 Full Analysis:** Run on 225-pair sample (mocked DeepSeek), verify pattern report generation
- **CLI Test:** Verify `python -m dedupe.analysis.pattern_discovery --help` works

**Manual Testing:**
- **Phase 2:** Human labeling of 30 pairs (calibration set)
- **Phase 3:** Human review of low-confidence LLM labels (~30-50 pairs)
- **Phase 3:** Human spot-check of high-confidence labels (15-20 pairs)
- **Phase 4:** Domain expert review of pattern report recommendations

**Test Data:**
- Use synthetic test data for unit tests (don't require real modular_results.csv)
- Use small sample (100 pairs) from real data for integration tests
- Use full dataset (170k pairs) for acceptance testing

**Continuous Testing:**
- Run `pytest tests/test_clustering.py tests/test_llm_labeling.py` on every code change
- Run `pytest tests/test_business_rules.py` after any scoring.py modifications
- Regression tests prevent breaking validated pairs when rules evolve

### Notes

**Critical Implementation Decisions:**

0. **Why k=15 clusters?**
   - Initial estimate from brainstorming session analyzing scoring.py rule combinations
   - 16 match types × 4 gate combinations × 6 data quality states = theoretical 384 combinations
   - Most combinations are invalid/rare, estimated ~15-20 meaningful patterns occur in practice
   - k=15 balances granularity (enough clusters to separate patterns) vs sample size (15 pairs per cluster = 225 total manageable for manual review)
   - **Validation required**: Silhouette analysis on k=5-30 will confirm optimal k; if k=8 or k=22 scores higher, use that instead
   - **Decision criteria**: Choose k with highest Silhouette score ≥0.3; if tie, prefer lower k for simpler interpretation

1. **K-means is fundamentally inappropriate** for boolean features
   - Research: IBM documentation, arxiv papers confirm k-means fails on categorical data
   - Must use k-modes with Hamming distance
   - This is a BLOCKING issue - do not proceed with k-means

2. **Rule Feature Extraction Complexity**
   - 35+ boolean features must be extracted from scoring.py logic
   - Each feature requires reverse-engineering the rule evaluation
   - High risk of misalignment between extracted features and actual rule behavior
   - Mitigation: Extensive unit tests comparing feature values to actual score_pair() results

3. **Interactive Phases Require User Availability**
   - Phase 2 (calibration): ~30 minutes for manual labeling
   - Phase 3 (full analysis): ~2-3 hours for manual review
   - Cannot be fully automated - requires domain expertise
   - Plan sessions when domain expert is available

4. **DeepSeek API Reliability**
   - Retry logic critical for handling API failures
   - Cost tracking important to avoid runaway expenses
   - Fallback: If DeepSeek fails completely, can fallback to manual labeling (slower, more expensive)

**Performance Expectations:**

- Clustering 170k pairs: <10 minutes (on modern CPU with n_jobs=-1)
- LLM labeling 225 pairs: <5 minutes (assuming 1-2 second API latency)
- Silhouette validation (k=5-30): ~5-10 minutes
- Pattern analysis: <5 minutes
- Total automated time: <30 minutes
- Total manual review time: 2-3 hours
- **End-to-end cycle: <4 hours**

**Cost Analysis:**

| Component | Cost | Notes |
|-----------|------|-------|
| DeepSeek API (225 pairs) | $0.04-0.10 | Research-validated estimate |
| Manual labeling (30 pairs, calibration) | ~$15-50 | 30-60 min at $30-50/hour |
| Manual review (low-confidence) | ~$30-100 | 1-2 hours |
| **Total per cycle** | **$45-160** | vs $112-937 for full manual |
| **Savings** | **71-85%** | Compared to manual annotation |

**Success Metrics:**

- **Discover 2-5 new rule opportunities per cycle** - Actionable recommendations
- **Reduce false positives by 10-20%** - Measurable improvement
- **Build ground truth dataset** - Growing by 200+ pairs per cycle
- **Pattern discovery cycle time** - <4 hours end-to-end
- **Cost per cycle** - <$200 (target: <$100)
- **Silhouette score** - ≥0.3 minimum, ≥0.5 target (well-defined clusters)

**Known Limitations:**

1. **Post-pipeline only** - Cannot discover patterns in real-time
2. **Requires modular_results.csv** - Cannot run without pipeline output
3. **Manual review bottleneck** - Human validation limits throughput
4. **Single LLM model** - No ensemble (cost vs accuracy tradeoff)
5. **Boolean features only** - Doesn't capture continuous similarity scores (future enhancement)

**Future Enhancements (Out of Scope):**

- Association rule mining (identify rule dependencies)
- Multi-LLM ensemble for higher accuracy
- Real-time pattern discovery during pipeline execution
- Automated rule generation (current: requires human approval)
- Advanced clustering (DBSCAN, hierarchical) for comparison
- Active learning to minimize labeling burden further

**Rollback Plan:**

- Analysis module is post-pipeline - does not affect production
- If issues arise, simply don't run the analysis module
- No production pipeline changes required
- Can delete `dedupe/analysis/` directory without impact
- Ground truth tests are optional - can be disabled if needed

**High-Risk Items (Pre-Mortem):**

1. **Risk:** Rule feature extraction doesn't match scoring.py behavior
   - **Mitigation:** Extensive unit tests, cross-validate with actual score_pair() results
   - **Impact:** Pattern analysis would be based on incorrect features (HIGH)

2. **Risk:** Silhouette score <0.3 indicates poor clustering
   - **Mitigation:** Test multiple k values, consider alternative algorithms
   - **Impact:** Clusters not meaningful, recommendations unreliable (MEDIUM)

3. **Risk:** DeepSeek API changes or becomes unavailable
   - **Mitigation:** OpenAI-compatible API, can switch to GPT-4 if needed
   - **Impact:** Higher cost, but functionality preserved (LOW)

4. **Risk:** Manual review takes >4 hours (user unavailable)
   - **Mitigation:** Can pause/resume phases, save intermediate results
   - **Impact:** Longer cycle time, but no data loss (LOW)

5. **Risk:** Pattern recommendations not actionable
   - **Mitigation:** Domain expert reviews before implementation
   - **Impact:** Wasted analysis effort, no rule improvements (MEDIUM)
