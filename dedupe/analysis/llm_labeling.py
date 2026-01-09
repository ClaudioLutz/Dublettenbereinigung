"""
DeepSeek LLM integration for entity pair labeling.

This module provides binary classification (DUPLICATE/NOT_DUPLICATE) using
the DeepSeek API via OpenAI-compatible client with confidence scoring.
"""

import os
import time
import json
from typing import Dict, List, Tuple
from dataclasses import dataclass
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv


@dataclass
class LabelResult:
    """Result from LLM labeling."""
    label: str  # "DUPLICATE" or "NOT_DUPLICATE"
    confidence: float  # 0.0 to 1.0
    reasoning: str
    pair_index: int = None
    model_used: str = "deepseek-chat"
    api_cost_estimate: float = 0.0


class CircuitBreaker:
    """Circuit breaker to prevent excessive API failures."""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.consecutive_failures = 0
        self.circuit_open_until = 0

    def record_success(self):
        """Reset circuit breaker on success."""
        self.consecutive_failures = 0

    def record_failure(self):
        """Record failure and potentially open circuit."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.circuit_open_until = time.time() + self.timeout
            print(f"\nCIRCUIT BREAKER: Too many failures ({self.consecutive_failures}). "
                  f"Pausing API calls for {self.timeout} seconds.")

    def is_open(self) -> bool:
        """Check if circuit is open (API calls blocked)."""
        if self.circuit_open_until > time.time():
            return True
        if self.circuit_open_until > 0:  # Was open, now closed
            print("CIRCUIT BREAKER: Circuit closed, resuming API calls.")
            self.circuit_open_until = 0
            self.consecutive_failures = 0
        return False


class DeepSeekClient:
    """Client for DeepSeek API integration."""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        max_cost: float = 5.0
    ):
        """
        Initialize DeepSeek client.

        Args:
            api_key: DeepSeek API key (default: from DEEPSEEK_API_KEY env var)
            base_url: API base URL (default: from DEEPSEEK_BASE_URL env var)
            model: Model name (default: from DEEPSEEK_MODEL env var)
            max_cost: Maximum allowed cost per run in USD (default: $5.00)
        """
        # Load environment variables
        load_dotenv()

        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.base_url = base_url or os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.model = model or os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        self.max_cost = max_cost

        if not self.api_key:
            raise ValueError("DeepSeek API key not found. Set DEEPSEEK_API_KEY in .env file.")

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # Track usage
        self.total_cost = 0.0
        self.total_requests = 0

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

    def label_pair(
        self,
        pair_data: Dict,
        few_shot_examples: List[Dict] = None
    ) -> LabelResult:
        """
        Get LLM label for a single entity pair.

        Args:
            pair_data: Dictionary with pair information (i, j, names, addresses, etc.)
            few_shot_examples: List of example pairs for few-shot prompting

        Returns:
            LabelResult with label, confidence, and reasoning

        Raises:
            Exception: If all retries are exhausted or circuit breaker is open
        """
        # Check circuit breaker
        if self.circuit_breaker.is_open():
            raise Exception("Circuit breaker is open. Too many consecutive API failures.")

        # Check cost ceiling
        if self.total_cost >= self.max_cost:
            raise Exception(f"Cost ceiling exceeded: ${self.total_cost:.2f} >= ${self.max_cost:.2f}")

        # Build prompt
        prompt = self._build_prompt(pair_data, few_shot_examples or get_default_few_shot_examples())

        # Retry logic
        max_retries = 3
        backoff_delays = [1, 2, 4]  # Exponential backoff

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert in entity resolution for Swiss person records. Your task is to determine if two records refer to the same person."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,  # Deterministic
                    response_format={"type": "json_object"}
                )

                # Parse response
                result_text = response.choices[0].message.content
                result_json = json.loads(result_text)

                # Validate response structure
                if 'label' not in result_json or 'confidence' not in result_json:
                    raise ValueError(f"Invalid response structure: {result_json}")

                label = result_json['label'].upper()
                if label not in ['DUPLICATE', 'NOT_DUPLICATE']:
                    raise ValueError(f"Invalid label: {label}")

                confidence = float(result_json['confidence'])
                if not (0.0 <= confidence <= 1.0):
                    raise ValueError(f"Invalid confidence: {confidence}")

                reasoning = result_json.get('reasoning', 'No reasoning provided')

                # Estimate cost (rough approximation: ~$0.0004 per pair)
                cost_estimate = 0.0004
                self.total_cost += cost_estimate
                self.total_requests += 1

                # Record success
                self.circuit_breaker.record_success()

                return LabelResult(
                    label=label,
                    confidence=confidence,
                    reasoning=reasoning,
                    model_used=self.model,
                    api_cost_estimate=cost_estimate
                )

            except Exception as e:
                print(f"API call failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    delay = backoff_delays[attempt]
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    # All retries exhausted
                    self.circuit_breaker.record_failure()
                    raise Exception(f"Failed after {max_retries} attempts: {e}")

    def label_batch(
        self,
        pairs: pd.DataFrame,
        few_shot_examples: List[Dict] = None,
        confidence_threshold: float = 0.85
    ) -> Tuple[pd.DataFrame, List[int]]:
        """
        Label multiple pairs with confidence filtering.

        Args:
            pairs: DataFrame with pair data
            few_shot_examples: List of example pairs for few-shot prompting
            confidence_threshold: Threshold for high confidence (default: 0.85)

        Returns:
            Tuple of (labeled_df, low_confidence_indices)
            - labeled_df: DataFrame with llm_label, llm_confidence, llm_reasoning columns
            - low_confidence_indices: List of indices requiring manual review
        """
        print(f"Labeling {len(pairs)} pairs with DeepSeek...")
        print(f"Confidence threshold: {confidence_threshold}")

        results = []
        low_confidence_indices = []

        for idx, row in pairs.iterrows():
            # Prepare pair data
            pair_data = row.to_dict()

            try:
                # Get label
                result = self.label_pair(pair_data, few_shot_examples)

                # Track low confidence
                if result.confidence < confidence_threshold:
                    low_confidence_indices.append(idx)

                results.append({
                    'llm_label': result.label,
                    'llm_confidence': result.confidence,
                    'llm_reasoning': result.reasoning
                })

                # Progress update
                if (idx + 1) % 25 == 0:
                    print(f"  Processed {idx + 1}/{len(pairs)} pairs "
                          f"(${self.total_cost:.4f} spent, "
                          f"{len(low_confidence_indices)} low-confidence so far)")

            except Exception as e:
                print(f"Error labeling pair {idx}: {e}")
                results.append({
                    'llm_label': 'ERROR',
                    'llm_confidence': 0.0,
                    'llm_reasoning': str(e)
                })
                low_confidence_indices.append(idx)

        # Combine results with original DataFrame
        results_df = pd.DataFrame(results)
        labeled_df = pd.concat([pairs.reset_index(drop=True), results_df], axis=1)

        print(f"\nLabeling complete:")
        print(f"  Total pairs: {len(pairs)}")
        print(f"  High confidence (>={confidence_threshold}): {len(pairs) - len(low_confidence_indices)}")
        print(f"  Low confidence (<{confidence_threshold}): {len(low_confidence_indices)}")
        print(f"  Total cost: ${self.total_cost:.4f}")

        return labeled_df, low_confidence_indices

    def _build_prompt(self, pair_data: Dict, few_shot_examples: List[Dict]) -> str:
        """Build few-shot prompt for entity pair classification."""
        # Extract pair fields
        first_i = pair_data.get('first_i', pair_data.get('vorname_i', ''))
        last_i = pair_data.get('last_i', pair_data.get('name_i', ''))
        first_j = pair_data.get('first_j', pair_data.get('vorname_j', ''))
        last_j = pair_data.get('last_j', pair_data.get('name_j', ''))

        address_i = f"{pair_data.get('street_i', '')} {pair_data.get('house_i', '')}, {pair_data.get('plz_i', '')} {pair_data.get('ort_i', '')}".strip()
        address_j = f"{pair_data.get('street_j', '')} {pair_data.get('house_j', '')}, {pair_data.get('plz_j', '')} {pair_data.get('ort_j', '')}".strip()

        dob_i = pair_data.get('dob_ymd_i', '')
        dob_j = pair_data.get('dob_ymd_j', '')

        prompt = f"""You are comparing two Swiss person records to determine if they refer to the same individual.

Few-shot examples:

"""

        # Add few-shot examples
        for ex in few_shot_examples:
            prompt += f"""Record A: {ex['record_a']}
Record B: {ex['record_b']}
Decision: {ex['label']}
Reasoning: {ex['reasoning']}

"""

        # Add current pair
        prompt += f"""Now classify this pair:

Record A:
  Name: {first_i} {last_i}
  Address: {address_i}
  DOB: {dob_i if dob_i else 'Unknown'}

Record B:
  Name: {first_j} {last_j}
  Address: {address_j}
  DOB: {dob_j if dob_j else 'Unknown'}

Respond with JSON only (no other text):
{{
    "label": "DUPLICATE" or "NOT_DUPLICATE",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation (1-2 sentences)"
}}
"""
        return prompt


def get_default_few_shot_examples() -> List[Dict]:
    """
    Get default few-shot examples for Swiss entity matching.

    Includes Swiss-specific patterns:
    - Compound surnames (hyphenated, maiden names)
    - Name order reversals (first/last swapping)
    - Extended surnames (multiple parts)
    - Umlaut variations

    Returns:
        List of example dicts with record_a, record_b, label, reasoning
    """
    return [
        {
            'record_a': 'Müller Hans, Bahnhofstrasse 12, 8001 Zürich, DOB: 1985-03-15',
            'record_b': 'Mueller Hans, Bahnhofstr. 12, 8001 Zurich, DOB: 1985-03-15',
            'label': 'DUPLICATE',
            'reasoning': 'Same person with umlauts/address variations but identical DOB and address.'
        },
        {
            'record_a': 'Weber-Meier Anna, Seestrasse 45, 6000 Luzern, DOB: 1990-07-22',
            'record_b': 'Weber Anna, Seestr. 45, 6000 Luzern, DOB: 1990-07-22',
            'label': 'DUPLICATE',
            'reasoning': 'Same person - compound surname variation (maiden name dropped) with matching DOB and address.'
        },
        {
            'record_a': 'Susette Ruppert-Schwarber, Bergstrasse 8, 4000 Basel, DOB: Unknown',
            'record_b': 'Susette Ruppert, Bergstr. 8, 4000 Basel, DOB: Unknown',
            'label': 'DUPLICATE',
            'reasoning': 'Same person - compound surname (Ruppert-Schwarber) vs single surname (Ruppert), same first name and address.'
        },
        {
            'record_a': 'Jorge Da Silva, Bahnhofplatz 3, 8000 Zürich, DOB: Unknown',
            'record_b': 'Silva Jorge, Bahnhofplatz 3, 8000 Zurich, DOB: Unknown',
            'label': 'DUPLICATE',
            'reasoning': 'Same person - name order reversed (first/last swapped) with matching address. Common in multi-cultural datasets.'
        },
        {
            'record_a': 'Maria Leonize Dias, Parkweg 12, 3000 Bern, DOB: Unknown',
            'record_b': 'Maria Leonize Dias Lobo Nobre, Parkweg 12, 3000 Bern, DOB: Unknown',
            'label': 'DUPLICATE',
            'reasoning': 'Same person - extended surname (Lobo Nobre added to Dias) with matching first names and address.'
        },
        {
            'record_a': 'Schmidt Peter, Hauptstrasse 5, 3000 Bern, DOB: Unknown',
            'record_b': 'Schmidt Petra, Hauptstrasse 5, 3000 Bern, DOB: Unknown',
            'label': 'NOT_DUPLICATE',
            'reasoning': 'Different first names (Peter vs Petra, different genders) at same address - likely family members, not duplicates.'
        },
        {
            'record_a': 'Schneider Thomas, Dorfstrasse 8, 9000 St. Gallen, DOB: 1978-11-05',
            'record_b': 'Schneider Thomas, Dorfstrasse 10, 9000 St. Gallen, DOB: 1978-12-05',
            'label': 'NOT_DUPLICATE',
            'reasoning': 'Different house numbers and different DOBs (month differs) suggest different individuals with common name.'
        }
    ]
