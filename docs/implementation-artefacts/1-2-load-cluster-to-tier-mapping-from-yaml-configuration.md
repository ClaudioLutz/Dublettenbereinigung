# Story 1.2: Load Cluster-to-Tier Mapping from YAML Configuration

Status: done

## Story

As a DevOps engineer,
I want the tier assignment logic to load cluster-to-tier mappings from a YAML configuration file,
So that I can update tier assignments without code changes when cluster validation results change.

## Acceptance Criteria

**AC1: YAML File Loading**
- **Given** a YAML configuration file exists at config/cluster_labels_v1.yaml
- **When** the tier assignment script starts
- **Then** the system loads the cluster-to-tier mapping (cluster ID -> Tier 1 or Tier 2)

**AC2: Cluster Coverage Validation**
- **Given** the YAML file is loaded
- **Then** the system validates that all 15 clusters (0-14) are mapped
- **And** unmapped clusters trigger a warning and default to Tier 2 (safe fallback)

**AC3: Configuration Logging**
- **Given** the YAML file is loaded successfully
- **Then** the system logs the loaded configuration version and cluster count
- **And** logs which clusters are mapped to Tier 1 and Tier 2

**AC4: Error Handling**
- **Given** an invalid YAML file or missing file
- **Then** the system triggers a clear error message with remediation guidance
- **And** on missing file, defaults all clusters to Tier 2 with warning

**AC5: Integration with Tier Assignment**
- **Given** the YAML config is loaded
- **When** tier assignment runs
- **Then** the system uses the loaded mapping instead of hardcoded FP rate thresholds
- **And** performance is not degraded (tier assignment still completes in <5 minutes)

## Tasks / Subtasks

- [x] Task 1: Create YAML configuration file schema (AC: 1,2)
  - [x] Create `config/cluster_labels_v1.yaml` with cluster-to-tier mappings
  - [x] Define schema: version, created_date, cluster_mappings (cluster_id -> tier)
  - [x] Document expected format with inline comments
  - [x] Include metadata: validation_date, model_version reference

- [x] Task 2: Implement YAML loader function (AC: 1,2,3,4)
  - [x] Create `load_cluster_tier_mapping()` function in generate_tiered_output.py
  - [x] Implement schema validation (check all 15 clusters present)
  - [x] Implement fallback logic for missing/invalid files
  - [x] Add comprehensive logging (version, cluster counts, tier distribution)
  - [x] Add type hints and docstrings

- [x] Task 3: Create unit tests for YAML loading (AC: 1,2,3,4)
  - [x] Test successful loading of valid YAML
  - [x] Test validation catches missing clusters
  - [x] Test fallback to Tier 2 for unmapped clusters
  - [x] Test error handling for missing file
  - [x] Test error handling for invalid YAML syntax
  - [x] Test error handling for wrong schema

- [x] Task 4: Integrate with tier assignment script (AC: 5)
  - [x] Create `classify_tiers_with_mapping()` function for YAML-based classification
  - [x] Update `main()` to load YAML config via --config argument
  - [x] Ensure backward compatibility (FP-rate based classification still works if no YAML)
  - [x] All 35 tests pass

- [x] Task 5: Create story documentation (AC: all)
  - [x] Story file created with comprehensive context
  - [x] Configuration file format documented in YAML comments
  - [x] Document how to update tier mappings

## Dev Agent Record

### Agent Model Used

claude-opus-4-5-20251101

### Implementation Approach

TDD (Test-Driven Development) - Red-Green-Refactor cycle

### Key Decisions

1. **Graceful Degradation**: Missing YAML file defaults all clusters to Tier 2 (safe fallback per NFR2.3)
2. **Schema Validation**: Validates cluster_tiers key exists, fills missing clusters with default tier
3. **Backward Compatibility**: --config argument is optional, FP-rate based classification remains default
4. **Comprehensive Logging**: Logs version, tier distribution, and any warnings about missing clusters

### Completion Notes

- All 5 Acceptance Criteria met
- 9 new tests added (6 for YAML loading, 3 for classification with mapping)
- 35 total tests passing
- YAML config created at config/cluster_labels_v1.yaml

### File List

**New Files Created:**
- config/cluster_labels_v1.yaml (YAML configuration with cluster-to-tier mappings)

**Files Modified:**
- scripts/generate_tiered_output.py (added load_cluster_tier_mapping, classify_tiers_with_mapping, --config arg)
- tests/test_tiered_output.py (added 9 new tests for Story 1.2)
- docs/implementation-artefacts/1-2-load-cluster-to-tier-mapping-from-yaml-configuration.md (this file)

### Change Log

- 2026-01-10: Story created with comprehensive context
- 2026-01-10: Implementation complete - 9 tests passing
- 2026-01-10: Status updated to "done"

## Dev Notes

### Critical Context from PRD & Epics

**Business Value:**
- Enables configuration-driven tier assignment without code changes
- Part of Epic 1: Automated Tier Assignment System
- Supports quarterly re-clustering workflow (Epic 6) where tier mappings change

**Key Requirements from PRD:**
- **FR1.2**: Cluster Label Mapping - Load cluster-to-tier mapping from YAML config, support updates without code changes
- **NFR2.3**: Fault Tolerance - Missing YAML defaults to Tier 2
- **NFR3.2**: Configuration Management - All config externalized to YAML, no hard-coded values

**Cluster-to-Tier Mapping (from validated results):**
- **Tier 1 (0% FP - Auto-Merge):** Clusters 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14
- **Tier 2 (>0% FP - Review):** Clusters 0, 1, 2, 5

### Architecture & Technical Requirements

**File Structure:**
```
config/
└── cluster_labels_v1.yaml    # NEW: Cluster-to-tier mapping config

scripts/
└── generate_tiered_output.py # MODIFIED: Add YAML loading
```

**YAML Schema Design:**
```yaml
# config/cluster_labels_v1.yaml
version: "1.0"
created_date: "2026-01-10"
validation_date: "2026-01-08"
model_version: "cluster_model_v1"

# Cluster-to-tier mapping
# Tier 1: 0% false positive rate (safe for auto-merge)
# Tier 2: >0% false positive rate (requires manual review)
cluster_tiers:
  0: 2   # Tier 2 - FP rate 15.2%
  1: 2   # Tier 2 - FP rate 8.7%
  2: 2   # Tier 2 - FP rate 12.3%
  3: 1   # Tier 1 - FP rate 0%
  4: 1   # Tier 1 - FP rate 0%
  5: 2   # Tier 2 - FP rate 5.1%
  6: 1   # Tier 1 - FP rate 0%
  7: 1   # Tier 1 - FP rate 0%
  8: 1   # Tier 1 - FP rate 0%
  9: 1   # Tier 1 - FP rate 0%
  10: 1  # Tier 1 - FP rate 0%
  11: 1  # Tier 1 - FP rate 0%
  12: 1  # Tier 1 - FP rate 0%
  13: 1  # Tier 1 - FP rate 0%
  14: 1  # Tier 1 - FP rate 0%
```

**Technology Stack:**
- PyYAML for YAML parsing
- pathlib for cross-platform paths
- typing for type hints

### Code Patterns

**YAML Loading Pattern:**
```python
from pathlib import Path
from typing import Dict, Optional
import yaml

def load_cluster_tier_mapping(
    config_path: Path,
    default_tier: int = 2
) -> Dict[int, int]:
    """
    Load cluster-to-tier mapping from YAML configuration.

    Args:
        config_path: Path to cluster_labels_v1.yaml
        default_tier: Default tier for unmapped clusters (default: 2)

    Returns:
        Dictionary mapping cluster ID (0-14) -> tier (1 or 2)

    Raises:
        ValueError: If YAML schema is invalid
    """
    if not config_path.exists():
        print(f"WARNING: Config file not found: {config_path}")
        print(f"Defaulting all clusters to Tier {default_tier}")
        return {i: default_tier for i in range(15)}

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Validate schema
    if 'cluster_tiers' not in config:
        raise ValueError(f"Invalid config: missing 'cluster_tiers' key")

    mapping = config['cluster_tiers']

    # Validate all clusters present
    for cluster_id in range(15):
        if cluster_id not in mapping:
            print(f"WARNING: Cluster {cluster_id} not in config, defaulting to Tier {default_tier}")
            mapping[cluster_id] = default_tier

    # Log configuration
    print(f"Loaded cluster config version: {config.get('version', 'unknown')}")
    tier1_clusters = [c for c, t in mapping.items() if t == 1]
    tier2_clusters = [c for c, t in mapping.items() if t == 2]
    print(f"  Tier 1 clusters: {tier1_clusters}")
    print(f"  Tier 2 clusters: {tier2_clusters}")

    return mapping
```

### Testing Requirements

**Unit Test Cases:**
1. `test_load_valid_yaml` - Successfully loads valid config
2. `test_load_missing_file` - Returns default mapping with warning
3. `test_load_invalid_yaml_syntax` - Raises clear error
4. `test_load_missing_clusters` - Fills missing with defaults
5. `test_load_wrong_schema` - Raises ValueError
6. `test_integration_with_classify_tiers` - Uses mapping instead of FP rates

### Previous Story Intelligence

**Story 1.1 Completed:**
- Created `scripts/generate_tiered_output.py` with FP-rate based tier classification
- Function `classify_tiers()` uses FP rate threshold (0.0) to determine tier
- This story will add YAML-based configuration as alternative/override

**Dependencies for Future Stories:**
- Story 2.1 will export cluster model to YAML (references this config format)
- Story 6.1 will generate new config versions during re-clustering
