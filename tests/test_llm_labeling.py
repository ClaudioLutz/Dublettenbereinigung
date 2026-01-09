"""
Unit tests for DeepSeek LLM integration module.

Tests cover:
- Prompt formatting with few-shot examples
- JSON response parsing
- Retry logic with exponential backoff (mocked)
- Confidence filtering
- Circuit breaker functionality
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from dedupe.analysis.llm_labeling import (
    DeepSeekClient,
    LabelResult,
    CircuitBreaker,
    get_default_few_shot_examples
)


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()

    # Valid JSON response
    mock_message.content = json.dumps({
        "label": "DUPLICATE",
        "confidence": 0.92,
        "reasoning": "Same person with minor address variation"
    })

    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    return mock_response


@pytest.fixture
def sample_pair_data():
    """Create sample pair data for testing."""
    return {
        'i': 0,
        'j': 1,
        'first_i': 'Hans',
        'last_i': 'Müller',
        'street_i': 'Bahnhofstrasse',
        'house_i': '12',
        'plz_i': '8001',
        'ort_i': 'Zürich',
        'dob_ymd_i': '19850315',
        'first_j': 'Hans',
        'last_j': 'Mueller',
        'street_j': 'Bahnhofstr.',
        'house_j': '12',
        'plz_j': '8001',
        'ort_j': 'Zurich',
        'dob_ymd_j': '19850315'
    }


def test_prompt_formatting(sample_pair_data):
    """Test that few-shot prompt is constructed correctly."""
    # Mock client (no actual API calls)
    with patch('dedupe.analysis.llm_labeling.OpenAI'):
        client = DeepSeekClient(api_key='test-key')

        few_shot_examples = get_default_few_shot_examples()
        prompt = client._build_prompt(sample_pair_data, few_shot_examples)

        # Verify prompt structure
        assert 'Few-shot examples' in prompt
        assert 'Record A:' in prompt
        assert 'Record B:' in prompt
        assert 'Hans' in prompt
        assert 'Müller' in prompt or 'Mueller' in prompt
        assert 'Bahnhofstrasse' in prompt or 'Bahnhofstr.' in prompt
        assert 'JSON' in prompt.lower()
        assert 'label' in prompt.lower()
        assert 'confidence' in prompt.lower()

        # Verify few-shot examples are included
        for ex in few_shot_examples:
            assert ex['label'] in prompt


def test_json_parsing(mock_openai_response):
    """Test that LLM response is parsed correctly."""
    with patch('dedupe.analysis.llm_labeling.OpenAI') as mock_openai:
        # Setup mock
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai.return_value = mock_client

        # Create client and label a pair
        client = DeepSeekClient(api_key='test-key')
        pair_data = {'first_i': 'Test', 'last_i': 'User'}

        result = client.label_pair(pair_data)

        # Verify result
        assert isinstance(result, LabelResult)
        assert result.label == 'DUPLICATE'
        assert result.confidence == 0.92
        assert 'variation' in result.reasoning


def test_json_parsing_with_invalid_response():
    """Test that invalid JSON responses are handled."""
    with patch('dedupe.analysis.llm_labeling.OpenAI') as mock_openai:
        # Setup mock with invalid JSON
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Invalid JSON {not valid}"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create client
        client = DeepSeekClient(api_key='test-key')
        pair_data = {'first_i': 'Test', 'last_i': 'User'}

        # Should raise exception after retries
        with pytest.raises(Exception):
            client.label_pair(pair_data)


def test_retry_logic():
    """Test that retry logic works with exponential backoff."""
    with patch('dedupe.analysis.llm_labeling.OpenAI') as mock_openai:
        with patch('time.sleep') as mock_sleep:  # Mock sleep to avoid delays
            # Setup mock to fail twice then succeed
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = [
                Exception("API Error 1"),
                Exception("API Error 2"),
                Mock(choices=[Mock(message=Mock(content=json.dumps({
                    "label": "DUPLICATE",
                    "confidence": 0.85,
                    "reasoning": "Test"
                })))])
            ]
            mock_openai.return_value = mock_client

            # Create client
            client = DeepSeekClient(api_key='test-key')
            pair_data = {'first_i': 'Test', 'last_i': 'User'}

            # Should succeed after 2 retries
            result = client.label_pair(pair_data)
            assert result.label == 'DUPLICATE'

            # Verify exponential backoff was used
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1)  # First retry
            mock_sleep.assert_any_call(2)  # Second retry


def test_confidence_filtering():
    """Test that high/low confidence pairs are filtered correctly."""
    with patch('dedupe.analysis.llm_labeling.OpenAI') as mock_openai:
        # Setup mock with varying confidence scores
        mock_client = Mock()

        # Create responses with different confidence levels
        def create_response(confidence):
            return Mock(choices=[Mock(message=Mock(content=json.dumps({
                "label": "DUPLICATE",
                "confidence": confidence,
                "reasoning": f"Confidence {confidence}"
            })))])

        mock_client.chat.completions.create.side_effect = [
            create_response(0.95),  # High confidence
            create_response(0.70),  # Low confidence
            create_response(0.88),  # High confidence
            create_response(0.60),  # Low confidence
        ]
        mock_openai.return_value = mock_client

        # Create client
        client = DeepSeekClient(api_key='test-key')

        # Create sample DataFrame
        pairs_df = pd.DataFrame([
            {'first_i': 'A', 'last_i': 'B'},
            {'first_i': 'C', 'last_i': 'D'},
            {'first_i': 'E', 'last_i': 'F'},
            {'first_i': 'G', 'last_i': 'H'},
        ])

        # Label batch with threshold 0.85
        labeled_df, low_confidence_indices = client.label_batch(
            pairs_df,
            confidence_threshold=0.85
        )

        # Verify filtering
        assert len(low_confidence_indices) == 2  # Two low confidence pairs
        assert 1 in low_confidence_indices  # Index 1 (0.70)
        assert 3 in low_confidence_indices  # Index 3 (0.60)
        assert len(labeled_df) == 4  # All pairs labeled


def test_circuit_breaker():
    """Test circuit breaker functionality."""
    breaker = CircuitBreaker(failure_threshold=3, timeout=60)

    # Initially closed
    assert not breaker.is_open()

    # Record failures
    breaker.record_failure()
    assert not breaker.is_open()

    breaker.record_failure()
    assert not breaker.is_open()

    breaker.record_failure()
    assert breaker.is_open()  # Opens after 3 failures

    # Should remain open
    assert breaker.is_open()

    # Record success resets counter
    breaker.record_success()
    assert not breaker.is_open()


def test_cost_ceiling():
    """Test that cost ceiling is enforced."""
    with patch('dedupe.analysis.llm_labeling.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content=json.dumps({
                "label": "DUPLICATE",
                "confidence": 0.9,
                "reasoning": "Test"
            })))]
        )
        mock_openai.return_value = mock_client

        # Create client with low max_cost
        client = DeepSeekClient(api_key='test-key', max_cost=0.001)

        # First call should succeed
        result1 = client.label_pair({'first_i': 'Test', 'last_i': 'User'})
        assert result1.label == 'DUPLICATE'

        # Second call should exceed cost ceiling
        with pytest.raises(Exception, match="Cost ceiling exceeded"):
            client.label_pair({'first_i': 'Test', 'last_i': 'User'})


def test_default_few_shot_examples():
    """Test that default few-shot examples have correct structure."""
    examples = get_default_few_shot_examples()

    assert len(examples) >= 2  # At least 2 examples

    for ex in examples:
        assert 'record_a' in ex
        assert 'record_b' in ex
        assert 'label' in ex
        assert 'reasoning' in ex
        assert ex['label'] in ['DUPLICATE', 'NOT_DUPLICATE']
        assert len(ex['reasoning']) > 0
