"""
Pattern Discovery Analysis Module for Entity Resolution.

This module provides tools for discovering rule patterns in matched pairs:
- K-modes clustering for categorical rule features
- LLM-based labeling with DeepSeek API
- Pattern analysis and report generation
- Regression testing framework

Main components:
- utils: Rule feature extraction and data loading
- clustering: K-modes clustering with validation
- llm_labeling: DeepSeek API integration
- pattern_report: Analysis and report generation
- pattern_discovery: Main orchestrator for all phases
"""

__version__ = "1.0.0"
