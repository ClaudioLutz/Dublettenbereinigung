# Story 2.3: Implement Cluster Classifier Module with No ML Dependencies

Status: done

## Story

As a DevOps engineer,
I want a cluster classification module that works without kmodes or sklearn dependencies,
So that the production tier assignment pipeline has minimal dependencies and faster startup.

## Acceptance Criteria

**AC1: No ML Dependencies**
- **Given** the cluster_classifier.py module is loaded
- **When** it's used for classification
- **Then** it works without importing kmodes or sklearn libraries

**AC2: Pure Python/NumPy Implementation**
- **Given** the classifier is initialized with centroids from YAML
- **When** classification runs
- **Then** only numpy and standard library are used for Hamming distance

**AC3: API Compatibility**
- **Given** existing code uses HammingDistanceClassifier
- **When** the module is updated
- **Then** the API remains unchanged (classify_pair, classify_batch)

**AC4: Import Verification**
- **Given** the module is imported
- **When** checking module dependencies
- **Then** no sklearn or kmodes imports exist in the module

## Tasks / Subtasks

- [x] Task 1: Audit current dependencies (AC: 1,4)
  - [x] Check cluster_classifier.py imports
  - [x] Verify no ML library dependencies (confirmed: only pathlib, typing, collections, logging, numpy, pandas, yaml)
  - [x] Document current state in this story

- [x] Task 2: Verify pure Python/NumPy implementation (AC: 2)
  - [x] Confirm Hamming distance uses only numpy (np.sum)
  - [x] Confirm classifier uses only numpy and pandas
  - [x] Add explicit imports check test

- [x] Task 3: Create verification tests (AC: all)
  - [x] Test module imports without kmodes/sklearn (2 tests)
  - [x] Test only allowed imports present (1 test)
  - [x] Test classifier works in isolation (1 test)

## Dev Agent Record

### Agent Model Used

claude-opus-4-5-20251101

### Implementation Approach

Verification and validation (module already uses pure NumPy)

### Key Decisions

1. **Already ML-Free**: The cluster_classifier.py was designed ML-free from Story 1.3
2. **Verification Tests**: Added 4 tests to verify and document the ML-free requirement
3. **Source Inspection**: Used Python's inspect module to verify imports at source level

### Completion Notes

- All 4 Acceptance Criteria verified
- 4 new verification tests added
- cluster_classifier.py imports: pathlib, typing, collections, logging, numpy, pandas, yaml
- NO kmodes or sklearn imports present
- 92 total tests passing

### File List

**Files Modified:**
- tests/test_cluster_classifier.py (added 4 verification tests)
- docs/implementation-artefacts/2-3-implement-cluster-classifier-module-with-no-ml-dependencies.md (this file)
- docs/implementation-artefacts/sprint-status.yaml

### Change Log

- 2026-01-10: Story created for Epic 2
- 2026-01-10: Verification tests added - 4 tests passing
- 2026-01-10: Status updated to "done"

## Dev Notes

### Critical Context from PRD & Epics

**Business Value:**
- Minimal dependencies = faster deployment and fewer security updates
- Production pipeline doesn't need ML training libraries
- Simpler containerization and deployment

**Key Requirements from PRD:**
- **FR2.3**: Cluster Classification - No ML training dependencies
- **NFR1.1**: Runtime Performance - Fast startup without heavy ML imports

### Architecture & Technical Requirements

**Expected State:**
The cluster_classifier.py module should:
- Import only: pathlib, typing, collections, numpy, pandas, yaml, logging
- NOT import: kmodes, sklearn, or any other ML training libraries

**Note:** The clustering.py module (in dedupe/analysis/) DOES use ML libraries for training.
Only the classifier module needs to be ML-free for production deployment.
