# Research Report: Using LLMs as Oracle for Entity Matching Ground Truth

## Summary

Comprehensive research on using Large Language Models (particularly DeepSeek, GPT-4, and Claude) for entity matching ground truth generation. This report covers LLM accuracy benchmarks, prompt engineering best practices, multi-LLM ensemble approaches, cost-benefit analysis, validation strategies, and patterns for converting LLM labels into regression tests.

## Research Context

- **Goal**: Use DeepSeek LLM for binary classification (DUPLICATE/NOT_DUPLICATE) of ~225 sampled pairs
- **Purpose**: Label samples to discover rule gaps and feed insights back into deterministic rules
- **Priority**: Cost optimization while maintaining high accuracy

---

## 1. LLM Accuracy for Entity Matching Tasks

### Performance Benchmarks

**Key Finding**: LLMs achieve at least **8% higher F1 performance** than the best transferred pretrained language models (PLMs), with GPT-4 outperforming the best PLM by **40% to 68%** on entity matching tasks.

**Fine-tuning Improvements**: Fine-tuned LLMs show substantial improvements of **1% to 26% F1** depending on the dataset, with the best fine-tuned models exceeding zero-shot GPT-4 performance by **1-10% F1** on four out of six datasets.

**Comparison to Traditional Methods**: GenAI approaches improved duplicate detection accuracy from **30% using traditional NLP techniques to almost 60%** using LLM-based methods on common benchmark datasets.

**Recent State-of-the-Art**: A method called LEMONADE (2025) outperforms the best baseline by up to **4.4 F1 points** on nine benchmark datasets while achieving approximately **10x faster inference** than traditional LLM-based methods.

### Model-Specific Comparisons

**GPT-4 Family**:
- GPT-4o achieved **86.21% precision** in customer support classification tasks
- GPT-4 offered the best overall reliability with an **F1 score of 81.60%**
- GPT-4o mini provides good performance at significantly lower cost

**Claude Family**:
- Claude 3.5 Sonnet achieved **85% precision** in classification tasks
- Generally **outperforms GPT and Gemini** in classification accuracy based on recent comparative studies
- Contract entity extraction showed 60-80% accuracy across most fields

**DeepSeek**:
- Agreement with GPT-4o on Entity A extraction: **37.36%**
- Agreement on Entity B extraction: **22.44%** (lower due to ambiguity)
- Category classification agreement with GPT-4o: **44.71%**
- **Outperforms Gemini, GPT, and Llama** in most cases but **underperforms Claude** in classification accuracy
- More cost-effective than OpenAI models (**27x cheaper** than OpenAI o1)

**Key Insight**: The moderate agreement between models (37-45%) suggests that **ensemble approaches may improve accuracy** by leveraging different models' strengths.

**Sources**:
- [Entity Matching using Large Language Models](https://arxiv.org/pdf/2310.11244)
- [Duplicate Detection with GenAI](https://arxiv.org/html/2406.15483v1)
- [Comparative Analysis of OpenAI GPT-4o and DeepSeek R1](https://arxiv.org/html/2503.02032v1)
- [Weakly-Supervised Entity Matching via LLM-Guided Data Augmentation](https://www.sciencedirect.com/science/article/abs/pii/S0950705125022725)
- [Comparison Analysis: Claude 3.5 Sonnet vs GPT-4o](https://www.vellum.ai/blog/claude-3-5-sonnet-vs-gpt4o)

---

## 2. Prompt Engineering Best Practices

### General Principles

**Research Finding**: The quality of LLM outputs significantly depends on how prompts are engineered, and **there is no single best prompt** - prompts need to be tuned for each model/dataset combination.

### Prompting Strategies for Entity Matching

**1. Zero-Shot Prompting**
- Basic approach: Direct question about whether two entity descriptions refer to the same entity
- Example structure: "Do these two records refer to the same person? Answer Yes or No."
- Suitable for well-defined, straightforward matching tasks

**2. Few-Shot Prompting**
- **Best Practice**: Include both duplicate and non-duplicate examples in the prompt
- Creates in-context learning to guide LLM responses with concrete examples
- Research shows LLMs require **no or only a few training examples** to perform comparably to PLMs fine-tuned with thousands of examples
- **Recommendation**: Start with 2-4 examples of each class (duplicate/non-duplicate)

**3. Chain-of-Thought (CoT) Prompting**
- Encourages LLMs to articulate their reasoning process
- Generates intermediate reasoning steps before final classification
- **Improvement**: Using CoT showed accuracy improvements from **30% to almost 60%** on duplicate detection benchmarks
- **Application**: While primarily effective for arithmetic/logical reasoning, CoT can improve entity matching by having the model explain similarities/differences before classifying

**Example CoT Prompt Structure**:
```
Compare these two records step by step:
1. Compare names
2. Compare addresses
3. Compare dates of birth
4. Evaluate overall match likelihood
5. Provide final classification (DUPLICATE/NOT_DUPLICATE)
```

**4. Structured Output Prompting**
- Request specific output format (e.g., JSON with classification + confidence score)
- Helps with downstream processing and threshold tuning
- Example: `{"classification": "DUPLICATE", "confidence": 0.92, "reasoning": "..."}`

### Cost-Efficient Prompt Engineering

**Key Research Finding**: The **"selecting strategy"** is the most cost-effective strategy for LLM-based entity matching, where the model selects from candidate matches rather than comparing all pairs.

**Best Practices for Cost Efficiency**:
- Use clear, concise prompts (fewer input tokens = lower cost)
- Leverage caching for repeated prompt structures (DeepSeek offers **up to 90% cost savings** with caching)
- Batch similar requests when possible
- Use smaller models (7B parameters) for simpler matching tasks

### Prompt Engineering Resources

**GitHub Repository**: [wbsg-uni-mannheim/MatchGPT](https://github.com/wbsg-uni-mannheim/MatchGPT) contains extensive prompt examples for entity matching experiments, including templates and variations.

**Sources**:
- [Cost-efficient prompt engineering for unsupervised entity resolution](https://link.springer.com/article/10.1007/s44163-024-00159-8)
- [Entity Matching with 7B LLMs: A Study on Prompting Strategies](https://ceur-ws.org/Vol-3931/paper4.pdf)
- [MatchGPT GitHub Repository](https://github.com/wbsg-uni-mannheim/MatchGPT)
- [Chain-of-Thought Prompting Guide](https://www.promptingguide.ai/techniques/cot)
- [Duplicate Detection with GenAI](https://medium.com/data-science/duplicate-detection-with-genai-ba2b4f7845e7)

---

## 3. Multi-LLM Ensemble Recommendations

### Ensemble Performance Benefits

**Key Finding**: A compound entity matching framework (ComEM) that leverages composition of multiple strategies and LLMs achieves improvements in **both effectiveness and efficiency** by benefiting from advantages of different approaches.

**Experimental Results**: Tests on 8 ER datasets and 10 LLMs verify the superiority of incorporating record interactions through the selecting strategy, as well as further cost-effectiveness brought by ComEM.

### Cost-Accuracy Trade-offs

**Benefits of Ensemble**:
- Combination of higher throughput, lower operational cost, and consistent interpretability
- Especially attractive for industrial-scale content management
- Can improve accuracy by **10%+** over single-model approaches

**Costs of Ensemble**:
- Principal trade-off: **computational cost** (multiple model evaluations required at inference time)
- Research spending: Studies have used **290+ dollars on OpenAI API calls** and **425+ GPU hours** for comprehensive testing
- Many existing solutions optimize a fixed cost-accuracy trade-off and are not easily customizable

### Ensemble Strategies

**1. Voting/Majority Rules**
- Run same input through multiple LLMs
- Take majority vote for final classification
- **Recommendation**: Use 3 models (odd number prevents ties)
- Best for high-stakes decisions where accuracy is critical

**2. Confidence-Based Selection**
- Use confidence scores from each model
- Select highest-confidence prediction
- Requires calibration of confidence scores per model

**3. Hierarchical/Cascading**
- Start with cheapest/fastest model
- Escalate to more expensive/accurate model only for uncertain cases
- **Cost Optimization**: Minimize compute while maintaining accuracy
- Example: DeepSeek (cheap) → GPT-4o mini (moderate) → Claude 3.5 Sonnet (expensive)

**4. Model Routing**
- Route different types of inputs to different models based on characteristics
- Requires upfront analysis of model strengths/weaknesses
- Most complex but potentially most cost-effective

### Recommendations for Your Use Case (225 Pairs)

**For Budget Optimization**:
- **Single Model**: DeepSeek-chat (cheapest, reasonable accuracy)
- **Dual Model**: DeepSeek + GPT-4o mini with disagreement resolution
- **Triple Ensemble**: DeepSeek + GPT-4o mini + Claude 3 Haiku (balance cost/accuracy)

**For Maximum Accuracy**:
- GPT-4o + Claude 3.5 Sonnet + DeepSeek R1 ensemble
- Use majority voting or confidence-weighted voting
- Estimate: ~$0.50-2.00 for all 225 pairs depending on record size

**Practical Approach**:
1. Start with single model (DeepSeek) on all 225 pairs (~$0.05-0.15 total)
2. Identify low-confidence predictions (e.g., confidence < 0.7)
3. Run ensemble only on uncertain cases (~50-75 pairs)
4. Total cost: ~$0.20-0.50 vs. ~$1.50-3.00 for full ensemble

**Sources**:
- [Match, Compare, or Select? An Investigation of LLMs for Entity Matching](https://aclanthology.org/2025.coling-main.8/)
- [ComEM GitHub Repository](https://github.com/tshu-w/ComEM)
- [Majority Rules: LLM Ensemble for Content Categorization](https://arxiv.org/pdf/2511.15714)
- [Harnessing Multiple Large Language Models: A Survey on LLM Ensemble](https://arxiv.org/html/2502.18036v1)

---

## 4. Cost-Benefit Analysis

### API Pricing Comparison (Per Million Tokens)

| Model | Input Cost | Output Cost | Cached Input | Notes |
|-------|-----------|-------------|--------------|--------|
| **DeepSeek-chat** | $0.27 | $1.10 | $0.07 | 27x cheaper than OpenAI o1 |
| **DeepSeek-reasoner** | $0.55 | $2.19 | $0.14 | Advanced reasoning, 90% cache savings |
| **GPT-4o mini** | $0.15 | $0.60 | - | Best value for high-volume tasks |
| **Claude Haiku 3** | $0.25 | $1.25 | - | Good balance |
| **Claude Haiku 3.5** | $0.80 | $4.00 | - | Latest version, higher cost |
| **GPT-4o** | ~$2.50 | ~$10.00 | - | Premium accuracy |
| **Claude 3.5 Sonnet** | ~$3.00 | ~$15.00 | - | Top-tier performance |

### Cost Per 1,000 Requests (Example Scenario)

**Assumptions**: 600 input tokens + 900 output tokens per request

- **DeepSeek-chat**: ~$0.16/day for 1,000 requests
- **GPT-4o mini**: ~$0.63/day for 1,000 requests
- **Claude Haiku 3.5**: ~$5.10/day for 1,000 requests

**For Your 225 Pairs**:
- **DeepSeek-chat**: $0.04-0.10 total
- **GPT-4o mini**: $0.15-0.30 total
- **Claude Haiku 3**: $0.30-0.60 total
- **Triple Ensemble**: $0.50-1.00 total (still very affordable)

### LLM Labeling vs. Manual Annotation

**Manual Annotation Costs**:
- Basic tasks: **$0.02-0.09 per object**
- Managed services: **$6-12 per hour**
- Complex tasks: **Up to $100 per example**
- Domain expertise required: Time-consuming and costly

**LLM Labeling Costs**:
- **225 pairs at $0.04-0.30**: Effectively free compared to manual labor
- **Time**: Minutes vs. hours/days for manual review
- **Scalability**: Can process thousands of pairs easily

**Cost Savings**:
- **80% reduction** in data labeling costs compared to traditional methods
- One approach achieved same alignment quality as full human labeling with **only ~6% of data being human-annotated**

### LLM + Active Learning Hybrid

**Most Cost-Effective Approach**:
1. Use LLM to label all 225 pairs (~$0.10)
2. Use confidence scores to identify uncertain cases (~30-50 pairs)
3. Manually review only uncertain cases (~$50-100 if outsourced, 1-2 hours if internal)
4. Use manual labels to validate LLM accuracy

**Research Results**:
- LLM-driven active learning retained **93% of GPT's classification performance** while requiring only **~6% of computational time and cost**
- Active learning can cut labeling effort by **30-70%** depending on domain complexity

### Return on Investment

**For Your Use Case**:
- **Cost**: $0.10-0.50 for LLM labeling
- **Benefit**: Discover rule gaps, improve deterministic rules, create regression test suite
- **Alternative Cost**: Manual review at ~$0.50-2.00 per pair = $112-450 total
- **ROI**: **224x - 4,500x cost reduction**

**Recommendation**: Use DeepSeek-chat for initial labeling, invest manual effort only on disagreements or low-confidence cases.

**Sources**:
- [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [Claude Haiku 4.5 vs GPT-4o mini vs Gemini Flash Pricing Comparison](https://skywork.ai/blog/claude-haiku-4-5-vs-gpt4o-mini-vs-gemini-flash-vs-mistral-small-vs-llama-comparison/)
- [LLM API Pricing Comparison 2025](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
- [Applying LLMs to Active Learning: Cost-Efficient Classification](https://onlinelibrary.wiley.com/doi/10.1155/int/6472544)
- [5 Best Data Annotation Companies in 2025](https://www.lightly.ai/blog/best-data-annotation-companies)

---

## 5. Validation Strategies for LLM Accuracy

### Human-LLM Collaborative Annotation

**Verifier Approach**:
- Objective: Identify potentially erroneous LLM-generated labels
- **Impact**: Verifiers can improve overall accuracy by **at least 10%** with only re-annotating **15% of "bad" labels**
- Avoids wasting human effort on re-annotating correct LLM labels

**Implementation**:
1. LLM generates initial labels for all 225 pairs
2. Verifier (could be another LLM or rule-based system) identifies suspicious labels
3. Human annotators validate only flagged subset
4. Iteratively improve LLM prompts based on error patterns

### Ground Truth Dataset Creation

**Golden Dataset Approach**:
- Build annotated "golden" dataset for experimentation
- Use for code-based and LLM-as-a-judge evaluations
- **Challenge**: Creating ground truth is time-consuming and requires human-in-the-loop
- **Hybrid Solution**: Use LLM to generate responses that humans review and edit

**For Your Use Case**:
1. LLM labels all 225 pairs
2. Randomly sample 20-30 pairs for human validation
3. Calculate agreement rate (precision/recall)
4. If agreement > 90%, accept LLM labels
5. If agreement < 90%, review additional pairs or adjust prompts

### LLM-as-a-Judge for Self-Validation

**Approach**:
- Use one LLM to generate labels, another LLM to evaluate quality
- Particularly useful when ground truth is extremely limited
- **Caution**: Must invest in calibrating evaluation prompts and watch for biases

**Implementation**:
1. Primary LLM (DeepSeek) labels all pairs
2. Judge LLM (GPT-4o mini or Claude) evaluates subset with confidence scoring
3. Flag low-confidence or disagreement cases for human review

**Pairwise Comparison Method**:
- Have LLM judge compare two different model predictions
- Determine which is more accurate based on criteria
- Use to select best model for your specific data distribution

### Claims Extraction Method

**Advanced Validation**:
1. LLM extracts all claims made in output (e.g., "names match", "addresses differ")
2. For each claim, ground truth verifies agreement
3. Enables fine-grained error analysis
4. Helps identify systematic LLM errors (e.g., always misses middle name variations)

### Confidence-Based Validation

**Calibration Process**:
1. LLM generates labels with confidence scores
2. On calibration set (20-30 human-labeled pairs), measure accuracy at different confidence levels
3. Determine threshold: e.g., "confidence > 0.8 = 95% accuracy"
4. Accept high-confidence labels automatically, review low-confidence labels

**Validation Types**:
- **With Ground Truth**: Compare LLM outputs to target reference answers
- **Without Ground Truth**: Directly assign quantitative scores or labels using LLM-as-a-judge

### Practical Validation Workflow for 225 Pairs

**Recommended Approach**:

**Phase 1: Calibration (30 pairs)**
1. Manually label 30 randomly selected pairs (gold standard)
2. Run LLM on same 30 pairs with confidence scores
3. Calculate precision, recall, F1 at different confidence thresholds
4. Identify error patterns (e.g., struggles with nickname variations)

**Phase 2: Full Labeling (195 remaining pairs)**
5. Run LLM on remaining 195 pairs
6. Automatically accept pairs with confidence > threshold (e.g., 0.85)
7. Flag low-confidence pairs for manual review

**Phase 3: Spot Checking**
8. Randomly sample 15-20 high-confidence LLM labels
9. Manually verify to ensure no systematic errors
10. If spot check accuracy > 95%, accept all high-confidence labels

**Phase 4: Continuous Improvement**
11. Track disagreements between LLM and manual reviews
12. Update prompts or switch models if patterns emerge
13. Rebuild calibration periodically as data evolves

**Expected Effort**:
- Manual labeling: 30-50 pairs (1-2 hours)
- LLM labeling: 225 pairs (5-10 minutes)
- Validation: 15-20 pairs (30 minutes)
- **Total human time**: 2-3 hours vs. 8-12 hours for full manual labeling

**Sources**:
- [Human-LLM Collaborative Annotation Through Effective Verification](https://dl.acm.org/doi/10.1145/3613904.3641960)
- [LLM Evaluation: A Beginner's Guide](https://www.evidentlyai.com/llm-guide/llm-evaluation)
- [Building an LLM Evaluation Framework: Best Practices](https://www.datadoghq.com/blog/llm-evaluation-framework-best-practices/)
- [LLMs as Oracles](https://www.emergentmind.com/topics/llms-as-oracles)
- [LLM Evaluation Metrics and Methods](https://www.evidentlyai.com/llm-guide/llm-evaluation-metrics)

---

## 6. Converting LLM Labels to Regression Tests

### Ground Truth Test Suite Creation

**Key Concept**: Build a labeled test set with reference answers for LLM regression testing. This "golden dataset" allows evaluation of every change against established benchmarks.

**Reference-Based Evaluations**: Rely on predefined correct answers (commonly called "reference," "golden," or "target" responses).

**Example**: For entity matching, the target response for comparing Person A and Person B is "DUPLICATE" or "NOT_DUPLICATE" with reasoning.

### Approaches for Converting LLM Labels to Test Cases

**1. Manual Labeling and Curation**
- Start small and keep adding examples as you discover new edge cases
- Label diverse scenarios: clear duplicates, clear non-duplicates, ambiguous cases
- **Best Practice**: Include examples that previously caused rule failures

**2. LLM-Generated Labels as Initial Test Cases**
- Use high-confidence LLM labels (e.g., confidence > 0.9) as regression tests
- Validate a sample to ensure quality
- Can help generate ground truth question-response pairs

**3. Human-LLM Alignment**
- Start with manually labeled examples (gold standard)
- Use LLM to scale up test suite
- Calibrate LLM outputs to agree with human judgments
- **Iterative Process**: Continuously refine based on real user interactions

### Regression Testing Workflow

**Typical Scenario**:
1. Create golden dataset with pre-approved responses
2. Establish baseline performance (e.g., 95% accuracy on test set)
3. Make a change (e.g., modify matching rules, update prompt)
4. Run tests against defined test cases
5. Verify outputs stay the same and quality remains high

**Implementation for Entity Matching**:
```python
# Example test case structure
test_cases = [
    {
        "id": "001",
        "record_1": {"name": "John Smith", "dob": "1980-01-15", ...},
        "record_2": {"name": "J. Smith", "dob": "1980-01-15", ...},
        "expected_label": "DUPLICATE",
        "expected_confidence": "> 0.8",
        "reasoning": "Same person, nickname variation",
        "rule_version": "v2.3"
    },
    # ... more cases
]
```

### Creating Comprehensive Test Suites

**Coverage Categories**:

**1. Clear Duplicates (30-40% of suite)**
- Exact matches with minor formatting differences
- Nickname variations
- Typos in non-key fields

**2. Clear Non-Duplicates (30-40% of suite)**
- Different people with similar names
- Same name, different DOB/address
- Common surnames

**3. Edge Cases (20-30% of suite)**
- Married name changes
- Address moves
- Data entry errors
- Missing fields
- Ambiguous cases

**4. Rule Boundary Cases (10% of suite)**
- Cases that specifically test rule thresholds
- Previously failed cases (regression prevention)
- Known challenging scenarios

### Evaluation Methods for Test Suite

**Reference-Based Automated Evaluation**:
- Compare LLM/rule outputs to known ground truth
- Use during experimentation, regression testing, and stress-testing
- Metrics: Precision, Recall, F1, Accuracy

**Correctness Evaluation**:
- Offline assessment where system compares response to "golden" reference
- Useful for experimental phase and regression testing after updates
- Can use LLM to compare (LLM-as-a-judge) or deterministic comparison

**Continuous Validation**:
- Run test suite on every rule change
- Track performance trends over time
- Alert on degradation (e.g., F1 drops below 90%)

### Practical Implementation for Your Project

**Phase 1: Build Initial Test Suite from LLM Labels**

1. **Run LLM on 225 Pairs**
   - Get labels + confidence scores + reasoning

2. **Stratify by Confidence**
   - High confidence (>0.9): 150 pairs → Auto-accept as test cases
   - Medium confidence (0.7-0.9): 50 pairs → Manual review
   - Low confidence (<0.7): 25 pairs → Definitely manual review

3. **Manual Validation**
   - Review all 75 medium+low confidence pairs
   - Randomly spot-check 20 high-confidence pairs
   - Create gold standard labels

4. **Build Test Categories**
   - Organize by duplicate type (exact, nickname, typo, etc.)
   - Organize by non-duplicate reason (different person, etc.)
   - Flag edge cases and difficult examples

**Phase 2: Create Regression Test Framework**

```python
# Example regression test structure
def test_entity_matching_rules():
    for test_case in load_test_suite():
        result = run_matching_rules(
            test_case['record_1'],
            test_case['record_2']
        )

        assert result['label'] == test_case['expected_label'], \
            f"Failed on {test_case['id']}: {test_case['description']}"

        assert result['confidence'] >= test_case['min_confidence'], \
            f"Low confidence on {test_case['id']}"
```

**Phase 3: Continuous Expansion**

- When rule changes are made, run full test suite
- When new edge cases are discovered, add to test suite
- When production errors occur, add to test suite as regression prevention
- Quarterly: Add diverse new samples to prevent overfitting

### Integration with Your Workflow

**Use LLM Labels to Discover Rule Gaps**:

1. **Disagreement Analysis**
   - Cases where LLM says DUPLICATE but rules say NOT_DUPLICATE (and vice versa)
   - Manually review disagreements to find rule gaps
   - **Key Insight**: These are your best test cases for regression testing

2. **Error Pattern Mining**
   - Group similar errors (e.g., "all gender-mismatched pairs")
   - Create business rules to handle patterns
   - Add representative examples to test suite

3. **Test-Driven Rule Development**
   - For each discovered gap, create failing test case first
   - Implement rule fix
   - Verify test passes + existing tests still pass
   - Classic TDD approach applied to business rules

**Recommended Test Suite Size**:
- **Minimum**: 100 diverse, validated test cases
- **Good**: 200-300 test cases covering major scenarios
- **Excellent**: 500+ test cases with comprehensive edge case coverage
- **Your Starting Point**: All 225 LLM-labeled pairs (after validation)

**Sources**:
- [LLM Testing in 2025: Top Methods and Strategies](https://www.confident-ai.com/blog/llm-testing-in-2024-top-methods-and-strategies)
- [A Tutorial on Regression Testing for LLMs](https://www.evidentlyai.com/blog/llm-regression-testing-tutorial)
- [LLM Regression Testing Workflow Step by Step](https://www.evidentlyai.com/blog/llm-testing-tutorial)
- [Testing for LLM Applications: A Practical Guide](https://langfuse.com/blog/2025-10-21-testing-llm-applications)
- [A Complete Guide to RAG Evaluation](https://www.evidentlyai.com/llm-guide/rag-evaluation)

---

## 7. Established Patterns: LLM as Oracle in Rule-Based Systems

### Generate-and-Check Pattern

**Core Concept**: The generate-and-check pattern requires an automated oracle to check responses for quality after generation. When quality doesn't suffice, feedback about failed checks can be fed back to the LLM to address identified shortcomings.

**Application to Entity Matching**:
1. Deterministic rules generate initial match predictions
2. LLM acts as oracle to validate uncertain cases
3. If validation fails quality check, feedback loop refines rules
4. Iterative improvement of rule-based system

**Limitation**: This pattern can only be applied to problems that have a verification mechanism. Otherwise, the model can easily hallucinate and build on its own hallucinations.

### LLMs-as-Oracle Concept

**Definition**: Replacing human-generated golden references with the output and feedback produced by large language models, treating them as authoritative benchmarks and learning signals for various tasks and applications.

**Key Capabilities**:
- Self-feedback as guidance for planning and decision-making
- Self-improving systems that refine rules based on LLM insights
- Authoritative validation of rule outputs

**Use Cases**:
- Validating business rule correctness
- Discovering edge cases in rule-based systems
- Generating synthetic test data
- Providing explanations for why rules should change

### Hybrid Systems: LLMs + Rule-Based Agents

**Pattern 1: Rule Preprocessing + LLM Semantic Analysis**
- Deterministic rule engine preprocesses structured inputs
- LLM performs semantic analysis and context-driven decision-making
- Combines speed of rules with flexibility of LLMs

**Pattern 2: LLM Draft + Rule-Based Feedback Loop**
1. LLM generates initial draft/classification
2. Rule-based agent provides feedback through Q&A dialogue
3. Iterative refinement until rules and LLM agree
4. User moderates disagreements

**Pattern 3: Deterministic Feedback Loops**
- Break task into smaller, manageable parts
- External logical loop (managed by rule system) handles iteration
- Pass each part to LLM while refining based on feedback
- **Key Advantage**: Overcomes LLM compute limitations through reasoning loops

### Feedback Loop Architecture

**Key Components**:

**1. LLM Oracle Layer**
- Provides authoritative classifications
- Generates confidence scores
- Explains reasoning

**2. Rule-Based System Layer**
- Applies deterministic matching rules
- Fast, predictable, explainable
- Handles clear-cut cases

**3. Feedback Mechanism**
- Captures disagreements between LLM and rules
- Logs explanations for differences
- Feeds insights back to rule developers

**4. Validation Layer**
- Human review of disagreements
- Arbitrates final ground truth
- Triggers rule updates

### Implementation Patterns for Your Use Case

**Pattern A: LLM as Validation Oracle**

```
For each of 225 pairs:
1. Run deterministic matching rules → prediction + confidence
2. If rules confidence < threshold (e.g., 0.8):
   - Escalate to LLM oracle
   - LLM provides classification + reasoning
3. If LLM and rules disagree:
   - Flag for manual review
   - Log as potential rule gap
4. Collect insights to improve rules
```

**Pattern B: LLM as Discovery Oracle**

```
1. LLM labels all 225 pairs with reasoning
2. Compare LLM labels to existing rule outputs
3. Disagreements = rule gap candidates
4. Analyze LLM reasoning for patterns
5. Implement new rules to handle patterns
6. Add to regression test suite
```

**Pattern C: Continuous Improvement Loop**

```
┌─────────────────────────────────────────┐
│ Production Entity Matching              │
│ - Deterministic rules handle 90% cases  │
│ - LLM oracle handles uncertain 10%      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Disagreement Detection                  │
│ - Flag cases where LLM differs from rules│
│ - Capture LLM reasoning                 │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Human Validation                        │
│ - Review flagged cases                  │
│ - Establish ground truth                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Rule Refinement                         │
│ - Implement new business rules          │
│ - Add cases to regression test suite    │
└──────────────┬──────────────────────────┘
               │
               └──────────────────────────┐
                                          │
                   (Loop back to Production)
```

### Best Practices for LLM-Rule Hybrid Systems

**1. Clear Separation of Concerns**
- Rules handle deterministic logic (exact matches, date comparisons)
- LLM handles semantic reasoning (nickname matching, fuzzy text similarity)
- Don't duplicate logic between systems

**2. Verification Mechanisms Required**
- LLM outputs must be verifiable (e.g., through manual review or consensus)
- Without verification, risk of hallucination cascade
- Implement confidence thresholds and human-in-the-loop for critical decisions

**3. Feedback Quality Matters**
- Generic feedback ("this is wrong") doesn't help LLM improve
- Specific feedback ("missed that 'Bob' is nickname for 'Robert'") enables learning
- Log detailed reasoning from LLM to understand failure patterns

**4. Gradual Automation**
- Start: LLM validates all rule outputs (discovery phase)
- Middle: LLM handles only uncertain cases (hybrid phase)
- End: Rules handle most cases, LLM for rare edge cases (production phase)
- Never fully eliminate human oversight

**5. Cost Optimization Through Routing**
- Use cheap models (DeepSeek) for bulk labeling
- Escalate to expensive models (Claude/GPT-4) only for disagreements
- Cache common patterns to reduce API calls

### Recommended Architecture for Your Project

**Phase 1: Discovery (Using 225 Sampled Pairs)**

```
Input: 225 sampled record pairs

Step 1: Existing Rules
→ Run current matching rules
→ Output: predictions + confidence scores
→ Collect: cases with low confidence (<0.7)

Step 2: LLM Oracle (DeepSeek)
→ Label all 225 pairs
→ Output: DUPLICATE/NOT_DUPLICATE + reasoning + confidence
→ Cost: ~$0.05-0.10

Step 3: Disagreement Analysis
→ Compare rule predictions vs. LLM predictions
→ Group disagreements by pattern (gender, nicknames, etc.)
→ Flag: 30-50 pairs with disagreements

Step 4: Human Validation
→ Review flagged disagreements
→ Establish ground truth for disagreements
→ Identify: "LLM was right" vs. "Rules were right" vs. "Both wrong"

Step 5: Rule Gap Analysis
→ For cases where LLM was right:
  - Analyze LLM reasoning
  - Identify missing business rule
  - Implement new rule
  - Add to regression test suite
```

**Phase 2: Production Integration**

```
Real-time Matching:
1. Apply deterministic rules (fast, cheap)
2. If confidence > 0.9 → Accept
3. If confidence < 0.9 → Escalate to LLM
4. If LLM confidence > 0.8 → Accept LLM result
5. If still uncertain → Human review queue

Feedback Loop:
- Log all LLM escalations
- Weekly review: Find new patterns
- Monthly: Update rules based on patterns
- Quarterly: Rebuild test suite
```

### Measuring Success

**Key Metrics**:
- **Rule Coverage**: % of cases handled by rules alone (target: 90%+)
- **LLM Agreement**: % of time LLM agrees with rules (target: 95%+)
- **False Positive Rate**: Incorrect duplicates (target: <2%)
- **False Negative Rate**: Missed duplicates (target: <5%)
- **Cost per Match**: API costs + compute (target: <$0.001 per pair)
- **Manual Review Rate**: % requiring human validation (target: <5%)

**Success Criteria for 225-Pair Exercise**:
- Identify: 3-5 new business rules or rule refinements
- Achieve: 90%+ agreement between refined rules and LLM oracle
- Create: Regression test suite with 225 validated pairs
- Document: Clear reasoning for each rule gap discovered

**Sources**:
- [Feedback Loops and Code Perturbations in LLM-based Software Engineering](https://arxiv.org/html/2512.02567v1)
- [Systems Design: How to Make LLMs Part of a Feedback Loop](https://www.hioscar.ai/13-systems-design-or-how-to-make-llms-part-of-a-feedback-loop)
- [OracleLLM: Empowering LLM with Self-Feedback](https://oracle-llm.github.io/)
- [Enhancing LLM Performance with Deterministic Feedback Loops](https://www.usekbai.com/blog/deterministic-ai-feedback-loops)
- [LLMs vs. Rule-Based Systems: Bridging AI with Deterministic Logic](https://blog.gopenai.com/llms-vs-deterministic-logic-overcoming-rule-based-evaluation-challenges-8c5fb7e8fe46)

---

## 8. Additional Considerations

### Confidence Scoring and Threshold Tuning

**Key Finding**: Confidence scores act as a "thermometer" indicating how likely the model is to be correct. Higher confidence scores mean more reliable outputs.

**Threshold Tuning**:
- As threshold increases, accuracy improves, but coverage decreases (trade-off)
- **Best Practice**: Set thresholds for acceptable confidence (e.g., only accept results with confidence > 0.80)
- Anything lower should be flagged for review
- Thresholds may need adjustment based on data characteristics

**Confidence Estimation Methods**:

1. **Logit-based confidence**: Examine model's output probabilities for each token
2. **Self-evaluation**: Run model multiple times with different random seeds, measure consistency
3. **Ensemble methods**: Use variance across multiple models as uncertainty indicator

**Calibration Methods**:
- **Temperature Scaling**: Adjusts overconfident predictions using single parameter
- **Isotonic Regression**: Fits monotonic function to recalibrate scores (requires large dataset)

**Practical Application**:
- Estimate LLM's confidence alongside labels
- Calibrate model's label quality (% agreement with ground truth) at each confidence score
- Decide operating point (confidence threshold)
- Reject all labels below threshold for manual review

### Active Learning for Sample Selection

**Key Concept**: Uncertainty sampling selects instances for which the model's current prediction is maximally uncertain.

**Uncertainty Measures**:
- **Classification Uncertainty**: Select samples with highest uncertainty
- **Classification Margin**: Select samples with smallest decision margin
- **Entropy**: Measure information uncertainty

**Combining Uncertainty with Diversity**:
- Problem: Top uncertain samples may be very similar (redundant information)
- Solution: Sample by uncertainty AND density (SUD)
- Use k-Nearest-Neighbor-based density to avoid outliers
- Optimize integration of uncertainty and diversity

**Application to Entity Matching**:
- Risk sampling leverages misprediction risk estimation
- Framework significantly outperforms baselines with limited label budget
- Especially effective for highly imbalanced classes

**Recommended for Your Project**:
1. LLM labels all 225 pairs with confidence scores
2. Select 30 highest-uncertainty pairs for human validation
3. Select 15 diverse low-uncertainty pairs (to avoid bias)
4. Use 45 validated pairs to calibrate confidence thresholds
5. Auto-accept remaining high-confidence pairs

---

## 9. Summary of Recommendations

### For Your Specific Use Case (225 Pairs, Cost-Optimized)

**Recommended Approach**:

**Model Selection**:
- **Primary**: DeepSeek-chat (best cost/performance ratio)
- **Validation**: GPT-4o mini for uncertain cases (if budget allows)
- **Estimated Cost**: $0.05-0.20 total

**Prompt Strategy**:
- Use few-shot prompting with 2 duplicate + 2 non-duplicate examples
- Request structured output: `{"label": "DUPLICATE|NOT_DUPLICATE", "confidence": 0.XX, "reasoning": "..."}`
- Consider CoT for complex/ambiguous pairs

**Validation Strategy**:
1. Manually label 30 randomly selected pairs (calibration set)
2. Run DeepSeek on all 225 pairs
3. Calculate accuracy on calibration set, establish confidence threshold
4. Auto-accept pairs with confidence > threshold (e.g., 0.85)
5. Manually review low-confidence pairs (~30-50 pairs)
6. Spot-check 15-20 high-confidence pairs for quality assurance

**Conversion to Test Suite**:
1. Use all 225 validated pairs as regression tests
2. Organize by duplicate type and edge case categories
3. Add test cases to version control
4. Run tests on every rule change
5. Expand test suite as new patterns emerge

**Feedback Loop**:
1. Compare LLM labels to existing rule outputs
2. Analyze disagreements for patterns (this is your goal!)
3. Prioritize rule gaps by frequency and business impact
4. Implement new rules or refinements
5. Verify new rules pass regression tests
6. Document reasoning in business rules documentation

**Expected Outcomes**:
- **Time**: 3-5 hours total (vs. 15-20 hours manual labeling)
- **Cost**: $0.05-0.30 (vs. $112-450 for manual annotation)
- **Deliverables**:
  - 225-pair labeled dataset with high confidence
  - 3-5 identified rule gaps with recommended fixes
  - Regression test suite for ongoing validation
  - Confidence calibration for future LLM use

### Key Takeaways from Research

1. **LLMs are Highly Effective for Entity Matching**: 40-68% better than traditional PLMs, approaching human-level accuracy

2. **Cost is Negligible**: For 225 pairs, LLM labeling costs $0.05-0.30 vs. $112-450 for manual annotation (224x-4,500x cheaper)

3. **Prompt Engineering Matters**: Few-shot prompting with diverse examples significantly improves accuracy; no single best prompt exists

4. **Ensemble Can Help But May Not Be Necessary**: For your scale (225 pairs), single model (DeepSeek) with manual validation of uncertain cases is most cost-effective

5. **Validation is Critical**: Always validate on a calibration set before trusting LLM labels at scale; 30-50 manually labeled pairs sufficient

6. **Confidence Scores Enable Optimization**: Use confidence thresholds to route only uncertain cases to manual review or expensive models

7. **LLM-Rule Hybrid is Best Pattern**: Use LLM as oracle to discover rule gaps, then implement deterministic rules for production; combines cost, speed, and explainability

8. **Test Suites are Valuable**: Converting LLM labels to regression tests provides ongoing value far beyond initial labeling exercise

9. **Feedback Loops Drive Improvement**: Continuous comparison of LLM insights with rule outputs reveals systematic gaps and enables iterative refinement

10. **DeepSeek is Excellent Choice**: 27x cheaper than OpenAI with reasonable accuracy; perfect for cost-sensitive labeling at your scale

---

## 10. Complete Source List

### LLM Accuracy & Benchmarks
- [Entity Matching using Large Language Models](https://arxiv.org/pdf/2310.11244)
- [Duplicate Detection with GenAI](https://arxiv.org/html/2406.15483v1)
- [The State Of LLMs 2025: Progress and Predictions](https://magazine.sebastianraschka.com/p/state-of-llms-2025)
- [LLM Benchmarks 2025 - Complete Evaluation Suite](https://llm-stats.com/benchmarks)
- [Top LLM Evaluation Benchmarks and How They Work](https://www.deepchecks.com/top-llm-evaluation-benchmarks-and-how-they-work/)
- [A Deep Dive Into Cross-Dataset Entity Matching](https://openproceedings.org/2025/conf/edbt/paper-224.pdf)
- [Weakly-Supervised Entity Matching via LLM-Guided Data Augmentation](https://www.sciencedirect.com/science/article/abs/pii/S0950705125022725)
- [Entity Matching with 7B LLMs: A Study on Prompting Strategies](https://ceur-ws.org/Vol-3931/paper4.pdf)

### Model Comparisons
- [ChatGPT vs Claude vs DeepSeek: Full Comparison](https://www.datastudios.org/post/chatgpt-vs-claude-vs-deepseek-full-report-and-comparison-on-features-capabilities-pricing-and-mo)
- [DeepSeek vs. ChatGPT vs. Claude: Comparative Study for Scientific Computing](https://www.sciencedirect.com/science/article/pii/S2095034925000157)
- [Comparative Analysis of OpenAI GPT-4o and DeepSeek R1](https://arxiv.org/html/2503.02032v1)
- [Comparison Analysis: Claude 3.5 Sonnet vs GPT-4o](https://www.vellum.ai/blog/claude-3-5-sonnet-vs-gpt4o)
- [GPT 5.1 vs Claude 4.5 vs Gemini 3: 2025 AI Comparison](https://www.getpassionfruit.com/blog/gpt-5-1-vs-claude-4-5-sonnet-vs-gemini-3-pro-vs-deepseek-v3-2-the-definitive-2025-ai-model-comparison)

### Prompt Engineering
- [Cost-efficient prompt engineering for unsupervised entity resolution](https://link.springer.com/article/10.1007/s44163-024-00159-8)
- [Cost-Efficient Prompt Engineering for Unsupervised Entity Resolution (arXiv)](https://arxiv.org/html/2310.06174v2)
- [MatchGPT GitHub Repository](https://github.com/wbsg-uni-mannheim/MatchGPT)
- [Prompt Engineering Best Practices: Tutorial & Examples](https://launchdarkly.com/blog/prompt-engineering-best-practices/)
- [Best practices for prompt engineering with OpenAI API](https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api)
- [PromptEM: prompt-tuning for low-resource generalized entity matching](https://dl.acm.org/doi/abs/10.14778/3565816.3565836)
- [The Ultimate Guide to Prompt Engineering in 2025](https://www.lakera.ai/blog/prompt-engineering-guide)

### Chain-of-Thought Prompting
- [Chain-of-Thought Prompting](https://learnprompting.org/docs/intermediate/chain_of_thought)
- [Chain-of-Thought Prompting Elicits Reasoning in LLMs](https://arxiv.org/abs/2201.11903)
- [Chain-of-Thought Prompting | Prompt Engineering Guide](https://www.promptingguide.ai/techniques/cot)
- [What is chain of thought (CoT) prompting? | IBM](https://www.ibm.com/think/topics/chain-of-thoughts)
- [Chain-of-Thought Prompting: Step-by-Step Reasoning with LLMs](https://www.datacamp.com/tutorial/chain-of-thought-prompting)
- [Duplicate Detection with GenAI (Medium)](https://medium.com/data-science/duplicate-detection-with-genai-ba2b4f7845e7)

### Multi-LLM Ensemble
- [Majority Rules: LLM Ensemble for Content Categorization](https://arxiv.org/pdf/2511.15714)
- [Match, Compare, or Select? An Investigation of LLMs for Entity Matching](https://aclanthology.org/2025.coling-main.8/)
- [ComEM GitHub Repository](https://github.com/tshu-w/ComEM)
- [Towards Efficient Multi-LLM Inference](https://arxiv.org/html/2506.06579v1)
- [Harnessing Multiple Large Language Models: A Survey on LLM Ensemble](https://arxiv.org/html/2502.18036v1)

### Cost & Pricing
- [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek API: A Guide With Examples and Cost Calculations](https://www.datacamp.com/tutorial/deepseek-api)
- [DeepSeek R1: Comparing Pricing and Speed Across Providers](https://prompt.16x.engineer/blog/deepseek-r1-cost-pricing-speed)
- [Claude Haiku 4.5 vs GPT-4o mini vs Gemini Flash Pricing Comparison](https://skywork.ai/blog/claude-haiku-4-5-vs-gpt4o-mini-vs-gemini-flash-vs-mistral-small-vs-llama-comparison/)
- [LLM API Pricing Comparison (2025): OpenAI, Gemini, Claude](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
- [GPT 4-o Mini vs Claude 3 Haiku vs Gemini 1.5 Flash: Pricing](https://www.vantage.sh/blog/gpt-4o-small-vs-gemini-1-5-flash-vs-claude-3-haiku-cost)

### Cost-Benefit & Active Learning
- [Applying LLMs to Active Learning: Cost-Efficient Classification](https://onlinelibrary.wiley.com/doi/10.1155/int/6472544)
- [Active Learning and Human Feedback for LLMs](https://intuitionlabs.ai/articles/active-learning-hitl-llms)
- [5 Best Data Annotation Companies in 2025](https://www.lightly.ai/blog/best-data-annotation-companies)
- [Active Learning Machine Learning: How It Reduces Labeling Costs](https://labelyourdata.com/articles/active-learning-machine-learning)
- [Learning from LLMs: Weak Labeling to Reduce Annotation Costs](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5901673)

### Validation & Evaluation
- [Human-LLM Collaborative Annotation Through Effective Verification](https://dl.acm.org/doi/10.1145/3613904.3641960)
- [LLM evaluation: a beginner's guide](https://www.evidentlyai.com/llm-guide/llm-evaluation)
- [Building an LLM evaluation framework: best practices](https://www.datadoghq.com/blog/llm-evaluation-framework-best-practices/)
- [The Definitive Guide to LLM Evaluation](https://arize.com/llm-evaluation/)
- [Evaluating LLM systems: Metrics, challenges, and best practices](https://medium.com/data-science-at-microsoft/evaluating-llm-systems-metrics-challenges-and-best-practices-664ac25be7e5)
- [LLMs as Oracles](https://www.emergentmind.com/topics/llms-as-oracles)
- [LLM Evaluation and Comparison in Label Studio](https://labelstud.io/blog/how-to-evaluate-and-compare-llms-using-prompts-in-label-studio/)
- [LLM evaluation metrics and methods](https://www.evidentlyai.com/llm-guide/llm-evaluation-metrics)

### Regression Testing & Test Suites
- [LLM Testing in 2025: Top Methods and Strategies](https://www.confident-ai.com/blog/llm-testing-in-2024-top-methods-and-strategies)
- [A tutorial on regression testing for LLMs](https://www.evidentlyai.com/blog/llm-regression-testing-tutorial)
- [LLM regression testing workflow step by step](https://www.evidentlyai.com/blog/llm-testing-tutorial)
- [LLM-as-a-judge: complete guide to using LLMs for evaluations](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [Testing for LLM Applications: A Practical Guide](https://langfuse.com/blog/2025-10-21-testing-llm-applications)
- [A complete guide to RAG evaluation](https://www.evidentlyai.com/llm-guide/rag-evaluation)

### LLM-Rule Hybrid Systems & Feedback Loops
- [Feedback Loops and Code Perturbations in LLM-based Software Engineering](https://arxiv.org/html/2512.02567v1)
- [Systems Design: How to Make LLMs Part of a Feedback Loop](https://www.hioscar.ai/13-systems-design-or-how-to-make-llms-part-of-a-feedback-loop)
- [LLM Feedback Loop](https://www.nebuly.com/blog/llm-feedback-loop)
- [OracleLLM: Empowering LLM with Self-Feedback](https://oracle-llm.github.io/)
- [The powerful LLM feedback loop is underrated](https://bdtechtalks.substack.com/p/the-powerful-llm-feedback-loop-is)
- [Feedback Loops in LLMOps: Catalyst for Continuous Improvement](https://medium.com/@t.sankar85/feedback-loops-in-llmops-the-catalyst-for-continuous-improvement-061fcad0bcd9)
- [Enhancing LLM performance with deterministic feedback loops](https://www.usekbai.com/blog/deterministic-ai-feedback-loops)
- [LLMs vs. Rule-Based Systems: Bridging AI with Deterministic Logic](https://blog.gopenai.com/llms-vs-deterministic-logic-overcoming-rule-based-evaluation-challenges-8c5fb7e8fe46)

### Confidence Scoring
- [Improve AI accuracy: Confidence Scores in LLM Outputs Explained](https://medium.com/@vatvenger/confidence-unlocked-a-method-to-measure-certainty-in-llm-outputs-1d921a4ca43c)
- [Confidence Scores in LLMs: Ensure 100% Accuracy](https://www.infrrd.ai/blog/confidence-scores-in-llms)
- [Measuring Confidence in LLM responses](https://medium.com/@georgekar91/measuring-confidence-in-llm-responses-e7df525c283f)
- [LLM Applications with Confidence Scoring](https://medium.com/@teckchuan/llm-applications-with-confidence-scoring-know-what-you-are-evaluating-cf1d58c0c899)
- [Improving data quality with confidence](https://www.refuel.ai/blog-posts/labeling-with-confidence)
- [5 Methods for Calibrating LLM Confidence Scores](https://latitude-blog.ghost.io/blog/5-methods-for-calibrating-llm-confidence-scores/)

### Active Learning & Uncertainty Sampling
- [Learning with not Enough Data Part 2: Active Learning](https://lilianweng.github.io/posts/2022-02-20-active-learning/)
- [Active Learning Using Uncertainty Information](https://arxiv.org/pdf/1702.08540)
- [Uncertainty sampling — modAL documentation](https://modal-python.readthedocs.io/en/latest/content/query_strategies/uncertainty_sampling.html)
- [How to measure uncertainty in uncertainty sampling for active learning](https://link.springer.com/article/10.1007/s10994-021-06003-9)
- [Active Deep Learning on Entity Resolution by Risk Sampling](https://chenbenben.org.cn/paper/youcef_KBS_2021.pdf)
- [Active Learning Sampling Strategies](https://medium.com/@hardik.dave/active-learning-sampling-strategies-f8d8ac7037c8)

### Additional Entity Resolution Resources
- [Building intelligent duplicate detection with Elasticsearch and AI](https://www.elastic.co/search-labs/blog/detect-duplicates-ai-elasticsearch)
- [Neo4j Live: Entity Resolution and Deduplication with GenAI](https://neo4j.com/videos/neo4j-live-entity-resolution-and-deduplication-with-neo4j-and-genai/)
- [Entity Resolution Explained: Top 12 Techniques](https://spotintelligence.com/2024/01/22/entity-resolution/)
- [Improving LLM accuracy with Entity RAG](https://tilores.io/content/improving-LLM-accuracy-in-regulated-industries-with-entity-resolution-based-RAG-EntityRAG)
- [Enhancing Entity Resolution Using Generative AI](https://medium.com/@reveriano.francisco/enhancing-entity-resolution-using-generative-ai-part-1-5c6fed1d037a)

---

## Document Metadata

- **Created**: 2026-01-07
- **Research Scope**: Web research conducted on 2026-01-07
- **Total Sources**: 100+ research papers, articles, and documentation pages
- **Focus Area**: LLM-based entity matching for ground truth labeling and rule discovery
- **Intended Use**: Guide implementation of LLM oracle for 225-pair duplicate detection exercise
