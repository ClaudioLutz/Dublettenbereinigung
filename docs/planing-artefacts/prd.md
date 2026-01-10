---
stepsCompleted: [1, 2, 3, 4, 6]
inputDocuments:
  - _bmad-output/analysis/brainstorming-session-2026-01-09.md
  - docs/research/pattern-discovery-research-20260107.md
  - docs/stories/20260107000000-llm-oracle-entity-matching-research.md
  - docs/END_TO_END_PIPELINE.md
  - docs/architecture.md
  - docs/businessrules.md
  - docs/index.md
workflowType: 'prd'
lastStep: 6
briefCount: 0
researchCount: 2
brainstormingCount: 1
projectDocsCount: 4
---

# Product Requirements Document - dubletten

**Author:** Claudio
**Date:** 2026-01-09

## Executive Summary

**dubletten** is a Swiss entity deduplication pipeline designed to identify and merge duplicate person records across a 7.5M+ record database with precision and efficiency. This PRD defines the completion and production integration of the **Pattern Discovery & Tiering System**, the final components needed to transform research prototypes into a production-ready automated deduplication workflow.

### Current State

The system currently operates as a 3-stage pipeline:
1. **Stage 1 (Production):** Rule-based deduplication using address-based blocking and 35+ Swiss-specific business rules, generating ~78k candidate pairs
2. **Stage 2 (Prototype Complete):** K-modes clustering and DeepSeek LLM validation, successfully identifying 11 clusters with 0% false positive rates
3. **Stage 3 (Missing):** Tier assignment and output generation

The pipeline achieves strong results (9.2% overall FP rate) but lacks production integration of validated clustering and automated tiered outputs.

### What This PRD Defines

This PRD specifies the implementation of three critical components that complete the end-to-end automated workflow:

1. **Tier Assignment System**
   - Generate auto-merge list (~20k pairs from 0% FP clusters)
   - Generate manual review queue (~45k pairs)
   - Implement configurable thresholds based on business requirements

2. **Production Integration**
   - Export k-modes model to YAML configuration (version-controlled, human-readable)
   - Integrate cluster classification into production deduplication runs
   - Enable model loading during runtime

3. **Continuous Improvement Loop**
   - Save LLM-validated pairs as regression test ground truth
   - Implement quarterly re-clustering workflow
   - Build feedback mechanism for rule refinement

### What Makes This Special

**1. LLM as One-Time Teacher, Not Production Dependency**
The architectural principle "use LLM to teach, encode knowledge, then fire the teacher" eliminates ongoing API costs while preserving pattern-learned accuracy. The system validates patterns with DeepSeek LLM once (~$0.07 per cycle), encodes the learnings into deterministic cluster-to-tier mappings, and runs production workloads without further LLM calls.

**2. Pattern Classification Unlocks 4x More Auto-Merges**
Pattern-based classification (k-modes clustering) identifies 20k auto-mergeable pairs versus ~5k with simple score thresholds—a 300% increase in automation. Critically, Cluster 7 (name-swapped patterns with 40% similarity scores) has 0% FP rate, revealing safe patterns that rule-based scoring alone would miss.

**3. Built for Evolution, Not Perfection**
The architecture explicitly supports the transition from LLM validation to human-labeled ground truth. The system starts with DeepSeek for rapid validation ($0.07/cycle), accumulates validated pairs as regression tests, and enables future migration to human labeling—without architectural rework.

**4. Integration of Existing Assets**
Rather than rebuilding from scratch, this implementation wires together completed components:
- ✅ Trained k-modes model (15 clusters)
- ✅ LLM-validated cluster labels (11 clusters with 0% FP)
- ✅ 78k pairs with cluster assignments
- ✅ Business rules with 35+ feature extraction

**Estimated effort:** 8-14 hours to production deployment.

## Project Classification

**Technical Type:** Data Pipeline / Scientific Computing
**Domain:** Data Science / Entity Resolution
**Complexity:** Medium
**Project Context:** Brownfield - completing partially-built functionality

**Classification Rationale:**

This is a **brownfield data pipeline project** in the **scientific computing** domain. The existing system demonstrates:
- Established Python-based architecture (dedupe/, scripts/, tests/ structure)
- Production-grade Stage 1 (rule-based scoring at scale)
- Research-validated Stage 2 (k-modes + LLM validation)
- Clear architectural patterns (blocking-first, business rule gates, YAML configs)

The new features integrate into this established architecture without fundamental restructuring. Complexity is **medium** due to:
- ML integration requirements (k-modes model persistence)
- LLM validation workflow (DeepSeek API)
- Pattern discovery system (clustering analysis)
- However: Established patterns, proven algorithms, and completed research reduce implementation risk

**Key Technical Context:**
- **Existing Tech Stack:** Python 3.x, SQL Server, LightGBM, k-modes, DeepSeek API, RapidFuzz
- **Architecture Pattern:** Three-stage pipeline with post-pipeline analysis
- **Performance Targets:** Process 7.5M records in ~60 minutes, generate outputs in <5 minutes
- **Quality Gates:** 0% FP guarantee for Tier 1 (auto-merge), <10% overall FP rate
- **Deployment Model:** Batch processing (monthly/quarterly cycles)

**Alignment with Existing Patterns:**
- **Model Persistence:** YAML configs (matches swisstopo database, business rules documentation pattern)
- **Validation Strategy:** Ground truth regression tests (aligns with existing test/ structure)
- **Output Format:** CSV files (consistent with modular_results.csv, clustered_results.csv)
- **Feedback Loop:** Ad-hoc re-clustering (realistic for team capacity, matches current operational model)

## Success Criteria

### User Success

**For Data Quality Teams (Primary Users):**

1. **Auto-Merge Confidence**
   - Users trust the Tier 1 auto-merge list completely (0% FP validation)
   - Users can execute merges without manual review for Tier 1 pairs
   - Users receive clear cluster-based explanations for each tier assignment

2. **Manual Review Efficiency**
   - Review queue reduced from 78k to ~45k pairs (42% reduction)
   - Tier 2 pairs presented with accurate confidence scores for prioritization
   - Users can focus review time on genuinely ambiguous cases

3. **System Transparency**
   - Users understand which cluster patterns are trusted vs. uncertain
   - Users can trace any pair's tier assignment back to its cluster characteristics
   - Users receive clear documentation on cluster profiles and FP rates

**Success Moment:** "I can confidently merge 20,000 duplicate pairs without fear of mistakes, and my manual review workload just dropped by nearly half."

### Business Success

**3-Month Success:**
- ✅ Stage 3 (Tier Assignment) deployed to production
- ✅ First production run generates tiered outputs successfully
- ✅ Auto-merge tier achieves 0% FP rate on validation sample
- ✅ Reduction in manual review burden validated (target: 40-45% reduction)

**12-Month Success:**
- ✅ Quarterly re-clustering workflow operational
- ✅ Ground truth dataset growing (800+ validated pairs accumulated)
- ✅ 2-3 business rule improvements identified and implemented
- ✅ Model persistence strategy proven stable across 4+ production cycles

**Key Business Metrics:**
- **Auto-Merge Volume:** ≥18,000 pairs per run (target: 20k)
- **Manual Review Reduction:** ≥40% reduction (from 78k to <47k)
- **False Positive Rate:** Tier 1 = 0%, Overall <10%
- **Operational Cost:** LLM validation cost <$0.50 per quarterly cycle
- **Staff Efficiency:** Review time per pair maintained or improved

### Technical Success

**Infrastructure:**
- Model persistence via YAML configs (version-controlled, human-readable)
- Production integration without architectural changes to Stage 1 or Stage 2
- Tier assignment script executes in <5 minutes for 78k pairs

**Quality:**
- Silhouette score for clustering ≥0.5 (well-defined clusters)
- K-modes clustering completes in <10 minutes for 170k pairs
- Regression test suite catches unintended rule changes

**Reliability:**
- End-to-end pipeline runtime ≤90 minutes (target: 60-75 minutes)
- Tier generation succeeds on all production runs
- Model loading from YAML configs without errors

**Maintainability:**
- Cluster-to-tier mappings updatable without code changes
- Re-clustering workflow executable by any team member
- Ground truth regression tests prevent breaking changes

### Measurable Outcomes

| Metric | Baseline | Target | Validation |
|--------|----------|--------|------------|
| **Auto-Merge Volume** | 0 pairs (manual) | 18k-22k pairs | Production run outputs |
| **Manual Review Burden** | 78k pairs | <47k pairs | Tier 2 output size |
| **Tier 1 FP Rate** | N/A | 0% | LLM validation sample |
| **Overall FP Rate** | 9.2% | <10% | Maintained or improved |
| **Pipeline Runtime** | ~60 min | <90 min | Maintained performance |
| **Tier Generation Time** | N/A | <5 min | Stage 3 execution time |
| **Implementation Effort** | 0 hours | 8-14 hours | Time to production |
| **LLM Validation Cost** | $0.07/cycle | <$0.50/cycle | Quarterly operating cost |

## Product Scope

### MVP - Minimum Viable Product

**Core Deliverables (8-14 hours):**

1. **Tier Assignment Script** (`scripts/generate_tiered_output.py`)
   - Input: Clustered results + LLM validation results
   - Logic: Assign pairs to Tier 1 (0% FP clusters) or Tier 2 (all others)
   - Output: `auto_merge_pairs.csv` and `review_queue_pairs.csv`
   - Validation: Verify Tier 1 contains only 0% FP clusters

2. **Model Persistence** (YAML Configuration)
   - Export k-modes cluster centroids to `models/cluster_model_v1.yaml`
   - Create cluster label mapping to `config/cluster_labels_v1.yaml`
   - Version control both configs with git

3. **Production Integration**
   - Add cluster classification to pipeline (`dedupe/cluster_classifier.py`)
   - Load model from YAML during dedup runs
   - Test end-to-end on historical data

4. **Basic Documentation**
   - Update `docs/END_TO_END_PIPELINE.md` with Stage 3 details
   - Create story file per CLAUDE.md requirements
   - Document cluster-to-tier mapping rationale

**MVP Success Criteria:**
- Tier 1 and Tier 2 outputs generated successfully
- Tier 1 validated to have 0% FP rate on sample
- Pipeline runtime impact <10 minutes
- All regression tests pass

### Growth Features (Post-MVP)

**Phase 2: Continuous Improvement (Quarter 2)**
1. **Ground Truth Management**
   - Save LLM-validated pairs to `ground_truth/` directory
   - Organize by category (clear_duplicates, clear_non_duplicates, edge_cases)
   - Expand regression test suite in `tests/test_business_rules.py`

2. **Quarterly Re-Clustering Workflow**
   - Document step-by-step re-clustering process
   - Create runbook for team execution
   - Automate cluster validation report generation

3. **Business Rule Improvements**
   - Implement score boost for swapped names (+20-30 points)
   - Fix compound surname gender-mismatch logic
   - Add Cluster 7 and Cluster 3 specific rules

**Phase 3: Enhanced Monitoring (Quarter 3)**
1. **Tier Assignment Monitoring**
   - Track auto-merge volume over time
   - Monitor Tier 1 cluster distribution
   - Alert on unexpected cluster FP rate changes

2. **Performance Dashboard**
   - Visualize cluster sizes and FP rates
   - Track ground truth dataset growth
   - Display rule improvement history

### Vision (Future)

**Long-Term Enhancements (6-12 months):**

1. **Human-Label Transition**
   - Migrate from DeepSeek validation to human-labeled ground truth
   - Build consensus labeling workflow for uncertain pairs
   - Compare human vs. LLM agreement rates

2. **Real-Time Prevention**
   - Extend batch pipeline to real-time duplicate detection
   - Deploy as API for data entry validation
   - Reuse cluster classification logic for live checking

3. **Advanced Pattern Discovery**
   - Implement association rule mining within clusters
   - Discover rule dependencies and redundancies
   - Auto-suggest new business rule candidates

4. **Multi-Dataset Generalization**
   - Test pipeline on other entity types (companies, addresses)
   - Create generalized deduplication framework
   - Package as reusable library

## User Journeys

### Journey 1: Anna Müller - From Drowning in Duplicates to Confident Automation

**The Data Quality Analyst Who Finally Trusts Automation**

Anna is a data quality analyst at a Swiss insurance company, responsible for maintaining the integrity of 7.5 million person records. Every month, she receives a list of 78,000 potential duplicate pairs and faces an impossible choice: manually review them all (400+ hours of work) or make risky batch decisions that could merge incorrect records and violate GDPR compliance. She's lost sleep over false positives that created customer service nightmares.

One Monday morning, Anna runs the upgraded deduplication pipeline with the new Pattern Discovery system. Instead of one massive 78,000-pair review queue, she receives two distinct files: `auto_merge_pairs.csv` (19,847 pairs) and `review_queue_pairs.csv` (44,218 pairs). Her heart races—can she really trust 20,000 auto-merges?

She opens the cluster report. Each auto-merge pair has a cluster label (3, 4, 6, 7, 8, 9, 10, 11, 12, 13, or 14) with documented 0% false positive rates validated by LLM analysis. She spot-checks 50 random pairs from Cluster 6 (exact matches, same address, same DOB)—perfect. She checks Cluster 7 (swapped names like "Silva Jorge" vs "Jorge Da Silva")—every single one is legitimate. The cluster explanations reveal patterns she never consciously coded but now trusts completely.

Anna makes her decision: she executes the auto-merge for all 19,847 Tier 1 pairs with a single command. Her manual review workload just dropped from 78,000 pairs to 44,218—a 43% reduction. Over the next two weeks, she reviews the Tier 2 queue (prioritized by confidence scores) and catches the genuinely ambiguous cases that genuinely need human judgment. Zero false positives escape to production from the auto-merge tier.

Three months later, Anna's monthly workload has transformed from 400 hours of soul-crushing review to 230 hours of focused, high-value judgment. She finally leaves work at 5 PM. Her manager asks how she's handling the workload—Anna smiles and says, "The system learned patterns I didn't know existed. I finally trust automation because I understand exactly why it's confident."

**Requirements Revealed:**
- Tier assignment system generating separate auto-merge and review queues
- Cluster-based explanations for every tier assignment
- Validation reports showing 0% FP rates per cluster
- Spot-check sampling tools for user confidence building
- Confidence score prioritization for Tier 2 review queue

---

### Journey 2: Thomas Schneider - Making the Business Case That Actually Sticks

**The Data Quality Manager Who Needs Proof, Not Promises**

Thomas manages the data quality team at a healthcare organization. His team has been using rule-based deduplication for three years, and every quarter he faces the same budget conversation: "Why do we pay for 2.5 FTEs to review duplicates?" He's tried to pitch automation before, but his CEO asked, "How do you guarantee zero mistakes?" Thomas had no answer. With GDPR and patient safety regulations, even a 1% error rate means lawsuits and regulatory fines.

When the engineering team proposes the Pattern Discovery system, Thomas is skeptical. "Another ML black box?" But the architect explains: "LLM validates patterns once, we encode the knowledge, then run production without ongoing AI costs. Zero false positives for auto-merge tier, guaranteed—we've validated it." Thomas demands proof.

The team runs Phase 2 LLM validation on 175 stratified sample pairs. The results come back: 11 clusters with 0% FP rate (validated by DeepSeek), 4 clusters with >0% FP rate (routed to manual review). Thomas reviews the validation methodology—Swiss-specific few-shot examples for compound surnames, name swapping, extended surnames. He spot-checks 30 pairs himself. The LLM caught edge cases even he would have missed.

Thomas runs the numbers: 20,000 auto-merge pairs × 2 minutes saved per pair = 667 hours saved per month = 1.6 FTEs freed up. Ongoing LLM cost: $0.07 per quarterly validation cycle. He brings the cluster validation report to his CEO: "We can confidently automate 25% of duplicates with mathematical proof of zero errors. The system shows its work—every decision is traceable to a validated pattern."

The CEO approves. Six months later, Thomas's team has processed 120,000 auto-merges with zero complaints, zero regulatory issues, and zero false positives. His quarterly budget review now starts with, "Your team's efficiency gains funded two new data analysts in other departments. What's next?"

Thomas's new problem: How to explain to other managers why their automation projects don't have the same guarantee of accuracy.

**Requirements Revealed:**
- LLM validation reports with statistical confidence metrics
- Ground truth regression testing framework
- Cost-benefit analysis dashboards (hours saved, LLM costs, FTE impact)
- Audit trail for every auto-merge decision with cluster rationale
- Quarterly re-validation workflow with trend analysis
- Compliance reporting (0% FP validation for regulatory audits)

---

### Journey 3: Lena Rodriguez - The DevOps Engineer Who Just Wants It to Work

**When Production Deployment Means "Load YAML, Not ML Models"**

Lena is a DevOps engineer managing the production data pipeline infrastructure. She's seen too many "ML-powered" features fail in production: missing model files, version mismatches, pickle compatibility issues, GPU dependencies on CPU-only servers. When data science says "We need to deploy our clustering model," Lena's first question is always: "What's going to break at 3 AM?"

The data science team presents the Pattern Discovery system architecture. Lena's relief is immediate when she sees the design: k-modes model exported to `models/cluster_model_v1.yaml`, cluster labels in `config/cluster_labels_v1.yaml`. No pickle files, no GPU requirements, no external API calls in production. "It's just YAML lookups?" she asks. "That's right," they confirm. "LLM teaches once, we encode knowledge, production runs deterministically."

Lena reviews the production integration plan:
1. Add `dedupe/cluster_classifier.py` (pure Python, no ML dependencies)
2. Load YAML configs at startup
3. Classify pairs by comparing feature vectors to cluster centroids
4. Generate tiered outputs

She tests the deployment on staging with historical data. The end-to-end pipeline runs: Stage 1 (60 minutes), Stage 2 classification (8 minutes), Stage 3 tier generation (90 seconds). Total runtime: 70 minutes, well within the 90-minute SLA. Memory usage: unchanged. CPU usage: +5% during classification. Zero external API calls. Perfect.

Lena deploys to production on a Friday afternoon—something she normally never does, but the simplicity gives her confidence. The Saturday morning cron job runs flawlessly. Tier 1: 19,847 pairs, Tier 2: 44,218 pairs, zero errors. She checks the logs: `Loaded cluster model from models/cluster_model_v1.yaml (15 clusters)`, `Classified 78,065 pairs in 8m 14s`, `Generated tiered outputs: auto_merge_pairs.csv (19847 rows), review_queue_pairs.csv (44218 rows)`.

Three months later, Lena gets a 2 AM page: "Dedup pipeline failed—file not found." She checks the logs: someone deleted `config/cluster_labels_v1.yaml` during cleanup. She restores from git, re-runs the pipeline, and it completes successfully. The issue was obvious, the fix was immediate, and the system degraded gracefully (defaulted all pairs to Tier 2 review).

Lena tells the data science team: "This is the first ML feature I've deployed where I'm not scared of the black box. I can debug it, I can version it, and it doesn't wake me up at night."

**Requirements Revealed:**
- YAML-based model persistence (human-readable, version-controlled)
- Graceful degradation when configs are missing
- Clear error messages with remediation guidance
- Runtime performance monitoring (classification time, memory usage)
- Version compatibility checks (model version vs. code version)
- Rollback strategy (revert YAML to previous version)
- Production runbook with troubleshooting flowchart

---

### Journey 4: Dr. Klaus Weber - The Stakeholder Who Finally Sees ROI

**The CTO Who Approved Budget and Needs Proof It Was Worth It**

Dr. Weber is the CTO of a Swiss financial services company. Last year, he approved a 120-hour budget (equivalent to 3 weeks of engineering effort) for "research into pattern discovery for deduplication." His CFO questioned the investment: "Why not just hire another data analyst?" Dr. Weber defended the initiative: "If it works, we save 1.6 FTEs permanently. If it doesn't, we learn something valuable."

Nine months later, Dr. Weber receives the quarterly data quality report. The numbers stop him mid-scroll:

**Before Pattern Discovery System:**
- Manual review burden: 78,000 pairs/month = 400 hours/month = 2.5 FTEs
- False positive rate: 9.2% (industry-leading, but still ~7,200 incorrect merges/month caught in post-review)
- LLM costs: $0 (no AI usage)
- Team morale: Low (repetitive work, fear of mistakes)

**After Pattern Discovery System (6 months of production):**
- Auto-merge volume: 20,000 pairs/month (0% FP rate, zero complaints)
- Manual review burden: 45,000 pairs/month = 230 hours/month = 1.4 FTEs
- False positive rate: 8.8% overall (improved through cluster-specific rule insights)
- LLM costs: $0.28/quarter ($0.07 × 4 validation cycles)
- Team morale: High ("Finally trust automation, focus on hard cases")

**ROI Calculation:**
- Effort saved: 1.1 FTEs = €88,000/year (Swiss salary + benefits)
- Implementation cost: €12,000 (120 hours × €100/hour blended rate)
- Ongoing operational cost: €1.12/year (LLM validation)
- **Net ROI: €75,888 annually, 633% return on investment**
- **Payback period: 1.6 months**

Dr. Weber forwards the report to the CFO with one line: "This is what good engineering looks like." The CFO replies: "What other processes can we apply this to?"

But Dr. Weber's favorite metric isn't on the report. It's the email from Anna, the data quality analyst: "I actually enjoy my job now. I'm solving puzzles, not drowning in repetition." That's the ROI he cares about most—teams that ship great work because they're empowered by great tools.

Six months later, Dr. Weber presents the Pattern Discovery system at a Swiss FinTech conference. His talk title: "LLM as Teacher, Not Production Dependency: How We Achieved 0% FP Automation for €1/year." Three companies ask for consulting engagements. Dr. Weber redirects them to his team with a single instruction: "Share everything—this should be how everyone solves entity resolution."

**Requirements Revealed:**
- Quarterly ROI dashboard (FTE hours saved, costs, FP rate trends)
- Morale and team satisfaction metrics
- Compliance audit trail (0% FP validation for regulators)
- Operational cost tracking (LLM validation spend)
- Business case templates for pitching similar initiatives
- Success metrics visualization (before/after comparison)

---

### Journey Requirements Summary

These four journeys reveal the complete capability set needed for the Pattern Discovery & Tiering System:

**Core Tiering Capabilities (Anna's Journey):**
- Tier 1 (auto-merge) and Tier 2 (review) output generation
- Cluster-based explanations for every pair assignment
- Spot-check sampling and validation tools
- Confidence score prioritization for manual review

**Validation & Compliance (Thomas's Journey):**
- LLM validation reports with statistical metrics
- Ground truth regression testing framework
- Audit trails for regulatory compliance
- Quarterly re-validation workflow
- Cost-benefit analysis dashboards

**Production Operations (Lena's Journey):**
- YAML-based model persistence (no ML runtime dependencies)
- Graceful degradation and error handling
- Production monitoring and troubleshooting runbooks
- Version control and rollback strategies
- Performance profiling (runtime, memory, CPU)

**Business Reporting (Dr. Weber's Journey):**
- ROI dashboards (FTE savings, costs, efficiency)
- Team morale and satisfaction tracking
- Quarterly executive summary reports
- Success metrics visualization
- Compliance and risk reporting

## Innovation & Novel Approaches

### Core Innovation: One-Shot LLM Knowledge Transfer

**The Problem with Traditional ML-Powered Deduplication:**
Most entity resolution systems using ML/LLM fall into one of two camps:
1. **Rule-based only**: Fast and deterministic, but miss nuanced patterns
2. **ML/LLM in production**: Capture nuance, but incur ongoing costs and complexity

**The Innovation:**
The Pattern Discovery system introduces a hybrid third approach: **"Use LLM to teach, encode knowledge, then fire the teacher."**

The system runs DeepSeek LLM validation once per quarter (~$0.07/cycle) to identify which k-modes clusters have 0% false positive rates. These cluster-to-tier mappings are then encoded into YAML configuration files and version-controlled. Production runs execute deterministically without any LLM calls, yet benefit from the pattern insights that LLM validation revealed.

**Why This Is Novel:**
- **Zero ongoing AI costs**: Production runs cost $0 for LLM (vs. $0.001-0.01 per pair for traditional LLM deduplication)
- **Deterministic and debuggable**: YAML configs are human-readable, version-controlled, and auditable
- **Combines best of both worlds**: Rule-based performance + pattern-learned accuracy

**Market Context:**
- Traditional entity resolution: Dedupe.io, Senzing, DataLadder (rule-based or supervised ML)
- LLM-powered deduplication: Emerging (2023-2024) but all use LLM per-pair in production
- **No known system uses LLM for one-time cluster validation with deterministic prod runtime**

### Pattern Discovery Innovation: Trust What You Wouldn't Code

**The Assumption Challenged:**
Traditional entity resolution assumes "low similarity scores = unsafe to auto-merge." Systems use hard thresholds (e.g., "only auto-merge pairs with >90% similarity").

**The Discovery:**
K-modes clustering revealed Cluster 7: name-swapped pairs like "Silva Jorge" vs "Jorge Da Silva" with average scores of 40%, yet LLM validation shows 0% false positive rate. These patterns are legitimate (Portuguese name conventions) but would never pass a 90% threshold.

**The Innovation:**
By clustering pairs by rule activation patterns (not scores), the system discovers which **pattern combinations** are safe, independent of similarity scores. This unlocks 4x more auto-mergeable pairs than threshold-based approaches.

**Why This Matters:**
- **20,000 auto-merge pairs vs. 5,000** with simple thresholds
- **Discovers unknown patterns**: Patterns a human wouldn't manually code (who knew 40% scores could be 100% safe?)
- **Continuous learning**: Quarterly re-clustering adapts to data evolution

### Architectural Innovation: Built for Transition

**The Typical Approach:**
Most systems choose validation method at design time: "We'll use LLM" or "We'll use human labelers." Switching later requires architectural rework.

**The Innovation:**
The Pattern Discovery system explicitly architects for the LLM → human-label transition:

1. **Phase 1 (Current)**: LLM validates clusters, system encodes learnings
2. **Phase 2 (Accumulation)**: LLM-validated pairs accumulate as ground truth regression tests
3. **Phase 3 (Transition)**: Switch to human consensus labeling, compare against LLM baseline
4. **Phase 4 (Maturity)**: Pure human-validated ground truth, LLM deprecated

**Why This Is Forward-Thinking:**
- **No rework required**: Same cluster-to-tier architecture works with any validation source
- **Graceful transition**: Can run LLM and human validation in parallel during transition
- **Realistic roadmap**: Acknowledges LLM limitations while leveraging current capabilities

### Validation Approach

**Validating the One-Shot LLM Approach:**

1. **Cost Validation** (Already Proven)
   - Measured: $0.07 per 175-pair validation cycle
   - Target: <$0.50 per quarterly cycle
   - **Status**: ✅ Validated (8x under budget)

2. **Accuracy Validation** (Already Proven)
   - Method: 175 stratified samples across 15 clusters
   - Result: 11 clusters with 0% FP rate, 4 clusters with >0% FP rate
   - **Status**: ✅ Validated (clear separation achieved)

3. **Production Validation** (To Be Proven)
   - Method: 6-month production deployment, track complaints
   - Target: Zero false positives from auto-merge tier
   - **Status**: 🔄 In progress (MVP deployment)

4. **Transition Validation** (Future)
   - Method: Human labeling on 500+ sample pairs, compare LLM vs. human agreement
   - Target: >85% agreement rate
   - **Status**: ⏸️ Planned for Quarter 3

**Fallback Strategy:**

If production validation fails (false positives detected in auto-merge tier):
1. **Immediate**: Move affected cluster(s) to Tier 2 (manual review)
2. **Investigation**: Re-run LLM validation with larger sample size
3. **Rule Update**: Refine business rules based on false positive patterns
4. **Re-Validation**: Quarterly re-clustering with updated rules

### Innovation Risks & Mitigation

**Risk 1: LLM Validation Accuracy Drift**
- **Concern**: DeepSeek model updates could change validation behavior
- **Mitigation**: Pin specific model version, save validation results as regression tests
- **Fallback**: Revert to previous validation if new model shows >10% disagreement

**Risk 2: Cluster Instability Over Time**
- **Concern**: Data evolution could shift cluster boundaries, invalidating 0% FP guarantees
- **Mitigation**: Quarterly re-clustering, track cluster silhouette scores, alert on >20% size changes
- **Fallback**: Re-validate affected clusters, demote to Tier 2 if FP rate increases

**Risk 3: Pattern Overfitting**
- **Concern**: Cluster patterns might not generalize to future data
- **Mitigation**: Ground truth accumulation (800+ pairs/year), ongoing monitoring
- **Fallback**: Expand Tier 2 review queue if auto-merge complaints increase

**Risk 4: Transition Friction (LLM → Human)**
- **Concern**: Human labelers might disagree with LLM patterns
- **Mitigation**: Start with high-agreement clusters, run parallel validation
- **Fallback**: Keep LLM validation for contentious clusters, use human labels for clear cases

## Functional Requirements

### FR1: Tier Assignment System

**FR1.1 - Generate Tiered Outputs**
- System SHALL read clustered results CSV with cluster assignments (0-14)
- System SHALL read LLM validation results CSV with FP rates per cluster
- System SHALL assign pairs to Tier 1 if cluster has 0% FP rate
- System SHALL assign pairs to Tier 2 if cluster has >0% FP rate
- System SHALL generate `auto_merge_pairs.csv` with Tier 1 pairs only
- System SHALL generate `review_queue_pairs.csv` with Tier 2 pairs only

**FR1.2 - Cluster Label Mapping**
- System SHALL load cluster-to-tier mapping from `config/cluster_labels_v1.yaml`
- System SHALL support updating mappings without code changes
- System SHALL validate mapping completeness (all 15 clusters mapped)
- System SHALL log unmapped clusters as warnings and default to Tier 2

**FR1.3 - Validation Reporting**
- System SHALL generate tier assignment report with statistics
- Report SHALL include: Tier 1 count, Tier 2 count, cluster distribution
- Report SHALL include: validation date, FP rates per cluster, silhouette score
- System SHALL save report to `_bmad-output/analysis/run_{timestamp}/tier_report.md`

### FR2: Model Persistence

**FR2.1 - Export K-Modes Model**
- System SHALL export k-modes cluster centroids to YAML format
- YAML SHALL include: cluster count, feature names (35 features), centroid values
- YAML SHALL be version-controlled with semantic versioning (v1, v2, etc.)
- System SHALL validate YAML schema on export

**FR2.2 - Load Model from YAML**
- System SHALL load k-modes model from `models/cluster_model_v1.yaml` at startup
- System SHALL validate model version compatibility with code version
- System SHALL gracefully degrade if model file missing (default all to Tier 2)
- System SHALL log model loading success/failure with details

**FR2.3 - Cluster Classification**
- System SHALL classify pairs by comparing feature vectors to cluster centroids
- System SHALL use Hamming distance for categorical feature matching
- System SHALL assign pair to cluster with minimum distance
- System SHALL add `cluster` column to results CSV (integer 0-14)

### FR3: Ground Truth Management

**FR3.1 - Save Validated Pairs**
- System SHALL save LLM-validated pairs to `ground_truth/` directory
- System SHALL organize by category: clear_duplicates, clear_non_duplicates, edge_cases
- System SHALL append to existing ground truth files (not overwrite)
- Each entry SHALL include: pair IDs, cluster, LLM label, confidence, validation date

**FR3.2 - Regression Testing**
- System SHALL load ground truth files in test suite
- Tests SHALL assert score ranges match historical behavior
- Tests SHALL fail if rule changes break validated patterns
- Tests SHALL generate diff report showing behavioral changes

### FR4: Production Integration

**FR4.1 - Cluster Classifier Module**
- System SHALL provide `dedupe/cluster_classifier.py` module
- Module SHALL expose `classify_pair(features)` function returning cluster ID
- Module SHALL support batch classification via `classify_batch(pairs_df)`
- Module SHALL have zero ML runtime dependencies (pure Python + NumPy)

**FR4.2 - End-to-End Pipeline Integration**
- Stage 1 (deduplication) SHALL run unchanged
- Stage 2 (classification) SHALL classify all pairs post-deduplication
- Stage 3 (tier assignment) SHALL generate tiered outputs
- Total pipeline runtime SHALL remain ≤90 minutes

**FR4.3 - Output File Format**
- Auto-merge CSV SHALL include: match_id, cluster, confidence, all record fields
- Review queue CSV SHALL include: match_id, cluster, confidence, all record fields
- Both CSVs SHALL be compatible with existing merge tools
- File encoding SHALL be UTF-8 with BOM for Excel compatibility

### FR5: Monitoring & Observability

**FR5.1 - Runtime Monitoring**
- System SHALL log cluster classification time per batch
- System SHALL log tier generation time and pair counts
- System SHALL track memory usage during classification
- System SHALL log warnings for performance degradation (>10 min for 78k pairs)

**FR5.2 - Quality Monitoring**
- System SHALL track auto-merge volume over time
- System SHALL alert if auto-merge volume drops >20% between runs
- System SHALL track cluster size distribution changes
- System SHALL alert if any cluster grows >50% between quarterly runs

**FR5.3 - Error Handling**
- System SHALL log all errors with stack traces
- System SHALL continue pipeline on non-critical errors (log + continue)
- System SHALL halt pipeline on critical errors (missing model, corrupt data)
- System SHALL provide remediation guidance in error messages

### FR6: Quarterly Re-Clustering Workflow

**FR6.1 - Re-Clustering Execution**
- System SHALL support manual re-clustering via CLI command
- Re-clustering SHALL run Phase 1 (k-modes) + Phase 2 (LLM validation)
- System SHALL generate new model version (increment v1 → v2)
- System SHALL preserve previous model version for rollback

**FR6.2 - Validation Comparison**
- System SHALL compare new FP rates to previous validation
- System SHALL highlight clusters with changed FP rates (0% → >0% or vice versa)
- System SHALL recommend tier mapping updates based on FP changes
- System SHALL generate migration guide for production deployment

### FR7: Business Reporting

**FR7.1 - ROI Dashboard**
- System SHALL calculate FTE hours saved (auto-merge count × 2 minutes)
- System SHALL track LLM validation costs per quarter
- System SHALL compute net ROI annually
- Dashboard SHALL visualize: before/after comparison, payback period

**FR7.2 - Executive Summary**
- System SHALL generate quarterly executive summary
- Summary SHALL include: auto-merge volume, FP rate, efficiency gains, costs
- Summary SHALL be exportable to PDF format
- Summary SHALL include charts: volume trends, FP rate trends, ROI trends

## Non-Functional Requirements

### NFR1: Performance

**NFR1.1 - Runtime Performance**
- End-to-end pipeline (Stage 1-3) SHALL complete in ≤90 minutes for 7.5M records
- Cluster classification SHALL complete in ≤10 minutes for 78k pairs
- Tier assignment SHALL complete in ≤5 minutes for 78k pairs
- Model loading from YAML SHALL complete in ≤30 seconds

**NFR1.2 - Scalability**
- System SHALL handle up to 10M records without architectural changes
- System SHALL support up to 200k matched pairs without performance degradation
- System SHALL support up to 30 clusters without code changes

**NFR1.3 - Resource Usage**
- Peak memory usage SHALL NOT exceed 16GB RAM
- CPU usage SHALL NOT exceed 80% average during classification
- Disk I/O SHALL NOT become bottleneck (use streaming where possible)

### NFR2: Reliability

**NFR2.1 - Availability**
- Pipeline SHALL have 99% success rate (99 successful runs per 100)
- Graceful degradation SHALL activate on model load failure
- System SHALL recover from transient errors without manual intervention

**NFR2.2 - Data Integrity**
- All generated CSVs SHALL pass schema validation
- Tier 1 pairs SHALL be validated against 0% FP guarantee
- No data loss SHALL occur during pipeline execution

**NFR2.3 - Fault Tolerance**
- Missing YAML config SHALL default to Tier 2 (safe fallback)
- Corrupt LLM validation results SHALL trigger re-validation warning
- Pipeline SHALL continue on non-critical errors with logging

### NFR3: Maintainability

**NFR3.1 - Code Quality**
- Code SHALL follow PEP 8 style guidelines
- All public functions SHALL have docstrings with type hints
- Code coverage SHALL be ≥80% for critical modules
- No code duplication (DRY principle)

**NFR3.2 - Configuration Management**
- All configuration SHALL be externalized to YAML files
- No hard-coded values in production code
- Configuration changes SHALL NOT require code deployment
- Version compatibility SHALL be validated at runtime

**NFR3.3 - Documentation**
- All public APIs SHALL have comprehensive docstrings
- README SHALL include: setup, usage, troubleshooting
- Runbooks SHALL exist for: deployment, rollback, re-clustering
- Architecture diagrams SHALL be kept up-to-date

### NFR4: Operability

**NFR4.1 - Deployment**
- Deployment SHALL require ≤30 minutes from code push to production
- Rollback SHALL be possible via git revert + model version downgrade
- Zero downtime deployment NOT required (batch pipeline)

**NFR4.2 - Monitoring**
- All errors SHALL be logged with severity levels
- Performance metrics SHALL be logged per run
- Alerts SHALL be triggered on: FP rate increase, volume drop, runtime spike

**NFR4.3 - Debuggability**
- Logs SHALL include: timestamps, severity, module, message, context
- Error messages SHALL include: remediation steps, relevant file paths
- Trace IDs SHALL link logs across pipeline stages

### NFR5: Security

**NFR5.1 - Data Privacy**
- PII SHALL NOT be logged (names, addresses, DOBs masked in logs)
- Ground truth files SHALL be stored with restricted permissions
- LLM API calls SHALL use encrypted connections (HTTPS)

**NFR5.2 - Access Control**
- Model YAML files SHALL be read-only for pipeline process
- Configuration files SHALL require admin privileges to modify
- Ground truth directory SHALL be writable only by pipeline process

**NFR5.3 - API Security**
- DeepSeek API key SHALL be stored in environment variables (not code)
- API calls SHALL include rate limiting and circuit breaker
- API responses SHALL be validated before processing

### NFR6: Usability

**NFR6.1 - User Interface (CLI)**
- CLI SHALL provide clear help text for all commands
- Progress indicators SHALL show during long operations
- Error messages SHALL be actionable (not cryptic)

**NFR6.2 - Output Formats**
- CSV outputs SHALL be Excel-compatible (UTF-8 with BOM)
- Reports SHALL be readable in plain text editors
- Dashboards SHALL be viewable in standard browsers

### NFR7: Compliance & Auditability

**NFR7.1 - Audit Trail**
- Every auto-merge decision SHALL be traceable to cluster + validation date
- Model version used SHALL be logged for each run
- Configuration changes SHALL be tracked in git history

**NFR7.2 - Reproducibility**
- Given same input + model version, pipeline SHALL produce identical outputs
- Random seeds SHALL be fixed for reproducible clustering
- All dependencies SHALL be pinned to specific versions

**NFR7.3 - Validation Evidence**
- LLM validation results SHALL be preserved for audit
- Ground truth pairs SHALL be immutable once validated
- Cluster FP rates SHALL be documented with sample evidence

## Technical Constraints

### TC1: Technology Stack

**TC1.1 - Programming Language**
- Python 3.9+ (existing codebase standard)
- No migration to other languages permitted

**TC1.2 - Dependencies**
- NumPy, Pandas (existing data processing stack)
- PyYAML (for model persistence)
- kmodes library (for clustering)
- RapidFuzz (for string similarity, existing)
- pytest (for testing, existing)

**TC1.3 - Prohibited Dependencies**
- No pickle files (security and compatibility risks)
- No GPU-only libraries (must run on CPU)
- No external databases for model storage

### TC2: Infrastructure

**TC2.1 - Deployment Environment**
- Production: Windows Server 2019+ OR Linux (Ubuntu 20.04+)
- CPU-only execution (no GPU required)
- 16GB RAM minimum, 32GB recommended

**TC2.2 - Data Storage**
- SQL Server for source data (existing)
- Local filesystem for models and outputs
- Git for version control (existing)

**TC2.3 - External Services**
- DeepSeek API for LLM validation (quarterly only)
- No other external dependencies

### TC3: Integration Constraints

**TC3.1 - Backward Compatibility**
- Stage 1 output format SHALL NOT change
- Existing merge tools SHALL work with new CSV outputs
- Existing tests SHALL continue to pass

**TC3.2 - API Stability**
- Public module APIs SHALL follow semantic versioning
- Breaking changes SHALL increment major version
- Deprecations SHALL have 2-quarter notice period

## Dependencies & Integrations

### D1: Internal Dependencies

**D1.1 - Existing Pipeline Components**
- **Stage 1** (dedupe/pipeline.py): Generates modular_results.csv
- **Stage 2** (dedupe/analysis/pattern_discovery.py): Generates clustered_results.csv
- **Format Converter** (dedupe/analysis/format_converter.py): Converts pair format

**D1.2 - Existing Business Rules**
- **Scoring Module** (dedupe/scoring.py): 35+ business rules for feature extraction
- **Feature Extraction** (dedupe/analysis/utils.py): Extracts boolean features for clustering

### D2: External Dependencies

**D2.1 - DeepSeek API**
- **Purpose**: LLM validation of cluster patterns (quarterly)
- **SLA**: Best-effort (no uptime guarantee)
- **Fallback**: Manual labeling if API unavailable
- **Cost**: ~$0.07 per 175-pair validation cycle

**D2.2 - SQL Server Database**
- **Purpose**: Source data for deduplication
- **SLA**: Existing production SLA
- **Impact**: Pipeline cannot run without database access

### D3: Tool Integrations

**D3.1 - Git Version Control**
- Model YAML files stored in git
- Configuration files version-controlled
- Deployment via git pull + restart

**D3.2 - Testing Framework**
- pytest for unit and integration tests
- Ground truth files as test fixtures
- CI/CD integration (future)

## Assumptions & Risks

### Assumptions

**A1: Data Assumptions**
- Input data quality remains stable (similar distribution to training data)
- Monthly deduplication volume stays within 50k-100k pairs range
- Address and name formats remain consistent with Swiss conventions

**A2: Operational Assumptions**
- Re-clustering can be performed quarterly (not real-time requirement)
- Manual review capacity can handle 45k pairs per month
- LLM API remains available and affordable (<$1/quarter)

**A3: Technical Assumptions**
- K-modes clustering remains effective for categorical features
- Hamming distance provides sufficient cluster separation
- YAML file I/O performance adequate for model loading

**A4: Business Assumptions**
- 0% FP guarantee for auto-merge tier is non-negotiable
- Team has capacity for quarterly re-validation
- Budget approved for LLM API costs (~$5/year)

### Risks

**R1: LLM Validation Accuracy Drift (MEDIUM)**
- **Description**: DeepSeek model updates could change validation behavior
- **Probability**: Medium (model providers update frequently)
- **Impact**: High (could invalidate FP guarantees)
- **Mitigation**: Pin specific model version, regression test validation results
- **Contingency**: Revert to previous validation, re-run with pinned model

**R2: Cluster Instability Over Time (MEDIUM)**
- **Description**: Data evolution shifts cluster boundaries, invalidating 0% FP guarantees
- **Probability**: Medium (data changes gradually)
- **Impact**: High (false positives in auto-merge tier)
- **Mitigation**: Quarterly re-clustering, silhouette score monitoring, FP rate alerts
- **Contingency**: Immediate demotion of affected clusters to Tier 2

**R3: Pattern Overfitting (LOW)**
- **Description**: Cluster patterns don't generalize to future data
- **Probability**: Low (validated on diverse samples)
- **Impact**: Medium (reduces auto-merge effectiveness)
- **Mitigation**: Ground truth accumulation (800+ pairs/year), ongoing monitoring
- **Contingency**: Expand Tier 2 review queue if complaints increase

**R4: Resource Capacity (LOW)**
- **Description**: Classification time exceeds 10-minute target as data grows
- **Probability**: Low (current: 8 minutes for 78k pairs)
- **Impact**: Medium (violates performance NFR)
- **Mitigation**: Profile and optimize Hamming distance calculation
- **Contingency**: Implement batch processing with parallelization

**R5: API Cost Escalation (LOW)**
- **Description**: DeepSeek pricing increases significantly
- **Probability**: Low (market is competitive)
- **Impact**: Low (quarterly cost <$1)
- **Mitigation**: Monitor pricing, cap API calls at 250 pairs max
- **Contingency**: Migrate to alternative LLM (GPT-4, Claude) or manual labeling

**R6: Team Turnover (LOW)**
- **Description**: Key team members leave, knowledge loss occurs
- **Probability**: Low (stable team)
- **Impact**: Medium (delays re-clustering and improvements)
- **Mitigation**: Comprehensive documentation, runbooks, knowledge transfer sessions
- **Contingency**: Hire/train replacement, lean on documented procedures

## Acceptance Criteria

### AC1: MVP Acceptance Criteria

**AC1.1 - Tier Assignment System**
- ✅ Tier 1 and Tier 2 outputs generated successfully
- ✅ Tier 1 contains only 0% FP clusters (validated)
- ✅ Tier 2 contains all remaining pairs
- ✅ Output files compatible with existing merge tools

**AC1.2 - Model Persistence**
- ✅ K-modes model exported to YAML format
- ✅ Cluster labels stored in `config/cluster_labels_v1.yaml`
- ✅ Model loads successfully at runtime without errors
- ✅ Both files version-controlled in git

**AC1.3 - Production Integration**
- ✅ End-to-end pipeline runs successfully on historical data
- ✅ Runtime impact <10 minutes (classification + tier generation)
- ✅ All existing regression tests pass
- ✅ No changes to Stage 1 output format

**AC1.4 - Documentation**
- ✅ END_TO_END_PIPELINE.md updated with Stage 3 details
- ✅ Story file created per CLAUDE.md requirements
- ✅ Cluster-to-tier mapping rationale documented

### AC2: Quality Gates

**AC2.1 - False Positive Guarantee**
- ✅ Tier 1 validation sample (n≥50) has 0% FP rate
- ✅ Each Tier 1 cluster independently validated (0% FP)
- ✅ Spot-check tool confirms 0% FP on random sample

**AC2.2 - Performance Targets**
- ✅ End-to-end pipeline completes in ≤90 minutes
- ✅ Classification completes in ≤10 minutes for 78k pairs
- ✅ Tier generation completes in ≤5 minutes

**AC2.3 - Volume Targets**
- ✅ Auto-merge volume ≥18,000 pairs per run
- ✅ Manual review reduction ≥40% (from 78k to <47k)

### AC3: Operational Readiness

**AC3.1 - Deployment Checklist**
- ✅ Deployment runbook created and tested
- ✅ Rollback procedure documented and tested
- ✅ Monitoring alerts configured
- ✅ Error handling verified (graceful degradation)

**AC3.2 - Team Readiness**
- ✅ Anna (Data Quality Analyst) trained on new outputs
- ✅ Thomas (Manager) received ROI dashboard training
- ✅ Lena (DevOps) comfortable with YAML-based deployment
- ✅ Dr. Weber (CTO) received executive summary

**AC3.3 - Support Materials**
- ✅ Troubleshooting guide created
- ✅ FAQ document published
- ✅ Spot-check sampling tool documented

### AC4: Success Validation (3-Month Post-Deployment)

**AC4.1 - User Success**
- ✅ Zero complaints about false positives in auto-merge tier
- ✅ Manual review workload reduced by ≥40%
- ✅ Data quality team reports increased confidence in automation

**AC4.2 - Business Success**
- ✅ Auto-merge volume averages ≥18,000 pairs per month
- ✅ FTE savings validated (≥1.0 FTE freed up)
- ✅ Quarterly LLM costs under budget (<$0.50)

**AC4.3 - Technical Success**
- ✅ Pipeline runtime consistently ≤90 minutes
- ✅ Zero production outages due to new components
- ✅ Regression tests catch 100% of breaking changes

---

## Document Control

**Document Version:** 1.0
**Last Updated:** 2026-01-09
**Author:** Claudio
**Status:** Complete - Ready for Implementation

**Approval:**
- [ ] Product Manager: _______________  Date: _______
- [ ] Technical Lead: _______________  Date: _______
- [ ] Data Quality Manager: _______________  Date: _______

**Revision History:**
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-09 | Claudio | Initial PRD complete (all 11 steps) |

---

**Next Steps:**
1. Review and approve PRD
2. Create Architecture Document (if needed) or proceed to Tech Spec
3. Create Epics & Stories from requirements
4. Begin MVP implementation (8-14 hours estimated)

**Related Documents:**
- [Brainstorming Session (2026-01-09)](_bmad-output/analysis/brainstorming-session-2026-01-09.md)
- [Pattern Discovery Research](docs/research/pattern-discovery-research-20260107.md)
- [END_TO_END_PIPELINE.md](docs/END_TO_END_PIPELINE.md)
- [Architecture Documentation](docs/architecture.md)
- [Business Rules](docs/businessrules.md)

---

**📋 PRD Complete - Pattern Discovery & Tiering System**
