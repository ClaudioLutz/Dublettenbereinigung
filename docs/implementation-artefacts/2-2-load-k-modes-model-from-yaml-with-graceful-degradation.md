# Story 2.2: Load K-Modes Model from YAML with Graceful Degradation

Status: done

## Story

As a DevOps engineer,
I want the production pipeline to load the k-modes model from YAML at startup with graceful degradation if the file is missing,
So that deployment failures are predictable and the system defaults to safe behavior.

## Acceptance Criteria

**AC1: Model Loading**
- **Given** the cluster classifier module is initialized
- **When** the system starts up
- **Then** the system attempts to load models/cluster_model_v1.yaml

**AC2: Successful Load**
- **Given** the file exists and is valid
- **When** the model loads
- **Then** the model loads successfully in ≤30 seconds
- **And** the system validates model version compatibility with code version

**AC3: Missing File Handling**
- **Given** the model file is missing
- **When** the system initializes
- **Then** the system logs a warning and defaults all pairs to Tier 2 (safe fallback)

**AC4: Corrupt File Handling**
- **Given** the model file is corrupt
- **When** the system attempts to load
- **Then** the system logs an error with remediation guidance and defaults to Tier 2

**AC5: Logging**
- **Given** model loading completes
- **Then** the system logs model loading status (success/failure), version, cluster count, and feature count

## Tasks / Subtasks

- [x] Task 1: Implement model loader function (AC: 1,2,5)
  - [x] Create `load_cluster_model()` function in dedupe/cluster_classifier.py
  - [x] Load model YAML with validation
  - [x] Return full model dict with centroids as Dict[int, np.ndarray]
  - [x] Log loading status and metadata
  - [x] Measure and verify load time ≤30 seconds

- [x] Task 2: Implement graceful degradation (AC: 3,4)
  - [x] Create `load_cluster_model_with_fallback()` function
  - [x] Handle FileNotFoundError → log warning, return None
  - [x] Handle corrupt YAML → log error with remediation, return None
  - [x] Create `create_tier2_fallback_classifier()` for safe fallback

- [x] Task 3: Create unit tests (AC: all)
  - [x] Test successful model load (2 tests)
  - [x] Test missing file returns None with warning
  - [x] Test corrupt file returns None with error
  - [x] Test load time performance (<30s)
  - [x] Test fallback classifier creation and behavior (3 tests)

## Dev Agent Record

### Agent Model Used

claude-opus-4-5-20251101

### Implementation Approach

TDD (Test-Driven Development) - Red-Green-Refactor cycle

### Key Decisions

1. **Full Model Return**: `load_cluster_model()` returns entire model dict, not just centroids, for access to metadata
2. **Logging Module**: Uses standard Python logging module for proper log levels (INFO, WARNING, ERROR)
3. **Remediation Guidance**: Error messages include specific remediation steps (re-export model or restore from git)
4. **Fallback Classifier**: `create_tier2_fallback_classifier()` creates single-centroid classifier for safe fallback

### Completion Notes

- All 5 Acceptance Criteria met
- 10 new tests added (2 model load, 4 fallback, 3 Tier 2 classifier, 1 performance)
- 88 total tests passing (Epic 1 + Story 2.1 + Story 2.2)
- Functions integrate with existing HammingDistanceClassifier

### File List

**Files Modified:**
- dedupe/cluster_classifier.py (added load_cluster_model, load_cluster_model_with_fallback, create_tier2_fallback_classifier)
- tests/test_cluster_classifier.py (added 10 new tests for Story 2.2)
- docs/implementation-artefacts/2-2-load-k-modes-model-from-yaml-with-graceful-degradation.md (this file)
- docs/implementation-artefacts/sprint-status.yaml

### Change Log

- 2026-01-10: Story created for Epic 2
- 2026-01-10: Implementation complete - 10 tests passing
- 2026-01-10: Status updated to "done"

## Dev Notes

### Critical Context from PRD & Epics

**Business Value:**
- Ensures production stability with predictable failure modes
- Safe fallback prevents incorrect auto-merges if model is missing
- Clear logging aids troubleshooting

**Key Requirements from PRD:**
- **FR2.2**: Load Model from YAML - Load k-modes model at startup, validate version compatibility, graceful degradation on failure
- **NFR2.1**: Availability - 99% pipeline success rate, graceful degradation on model load failure
- **NFR2.3**: Fault Tolerance - Missing YAML defaults to Tier 2

### Architecture & Technical Requirements

**Fallback Behavior:**
- If model missing → all pairs assigned to Tier 2 (safe, manual review)
- If model corrupt → all pairs assigned to Tier 2 (safe, manual review)
- Pipeline continues running, doesn't fail

**Logging Format:**
```
INFO: Loading cluster model from models/cluster_model_v1.yaml
INFO: Model loaded successfully (version: v1, clusters: 15, features: 35)
  or
WARNING: Cluster model not found: models/cluster_model_v1.yaml - defaulting to Tier 2
  or
ERROR: Corrupt cluster model: models/cluster_model_v1.yaml - missing 'centroids' key
       Remediation: Re-export model using export_cluster_model() or restore from git
```

### Code Patterns

**Loader Interface:**
```python
def load_cluster_model(model_path: Path) -> Dict[int, np.ndarray]:
    """Load and return centroids from YAML model file."""
    pass

def load_cluster_model_with_fallback(
    model_path: Path,
    logger: logging.Logger = None
) -> Optional[Dict[int, np.ndarray]]:
    """
    Load model with graceful degradation.

    Returns:
        Centroids dict if successful, None if failed (caller handles fallback)
    """
    pass
```

### Previous Story Intelligence

**Story 1.3 Completed:**
- Created `load_centroids_from_yaml()` in cluster_classifier.py
- This story enhances with graceful degradation and better logging

**Story 2.1 Completed:**
- Created `export_cluster_model()` that produces compatible YAML
- Created `validate_model_schema()` for validation
