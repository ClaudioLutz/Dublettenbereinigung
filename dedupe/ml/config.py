"""
Configuration constants for ML-based entity matching.

This module centralizes all ML configuration parameters for:
- Embedding model selection and parameters
- Text preparation strategies
- Memory and performance tuning
"""

# ==============================================================================
# Embedding Model Configuration
# ==============================================================================

# Sentence-transformer model
# paraphrase-multilingual-MiniLM-L12-v2 provides:
# - Multilingual support (German, French, Italian for Swiss addresses)
# - Lightweight (118M parameters, ~500MB)
# - Optimized for paraphrase/semantic similarity
# - Embedding dimension: 384
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

# Batch size for embedding generation
# For 4GB VRAM GPU: 256 is safe
# For CPU: reduce to 64-128 for better memory efficiency
BATCH_SIZE = 256

# Device for embedding generation
# Options: 'cuda' (GPU), 'cpu', 'auto' (auto-detect)
DEVICE = 'auto'  # Will auto-detect GPU if available

# ==============================================================================
# Text Preparation Strategy
# ==============================================================================

# Special tokens for field separation (helps model learn structure)
TOKEN_NAME = "[NAME]"
TOKEN_ADDR = "[ADDR]"
TOKEN_DOB = "[DOB]"

# Text concatenation template
# Fields are normalized (lowercase, umlauts converted, etc.) before embedding
TEXT_TEMPLATE = "{token_name} {first} {last} {name2} {token_addr} {street} {house} {plz} {ort}"

# Example output:
# "[NAME] hans mueller [ADDR] hauptstrasse 12 8000 zuerich"

# Include DOB in text (optional, can improve precision but reduces recall for typos)
INCLUDE_DOB_IN_TEXT = False  # Set to True to add "[DOB] {dob_ymd}" to template

# ==============================================================================
# FAISS Index Configuration
# ==============================================================================

# Index type: 'IVF' (Inverted File Index with clustering)
# Provides good balance of speed and accuracy for large datasets
FAISS_INDEX_TYPE = 'IVF'

# Number of clusters for IVF index
# Rule of thumb: ~sqrt(num_records)
# For 7.5M records: 1024-2048 is reasonable
FAISS_N_CLUSTERS = 1024

# Number of probes during search (higher = more accurate, slower)
# Default: n_clusters / 8
FAISS_N_PROBES = 128

# Sample size for index training (fraction of total data)
# Training on 10% is typically sufficient
FAISS_TRAIN_SAMPLE_FRACTION = 0.1

# ==============================================================================
# Storage Configuration
# ==============================================================================

# Memory mapping for large embedding arrays
# Embeddings are stored on disk and accessed via memory mapping
USE_MEMORY_MAPPING = True

# Embedding data type
# float32: Standard precision (4 bytes per value)
# float16: Half precision (2 bytes, may reduce quality slightly)
EMBEDDING_DTYPE = 'float32'

# ==============================================================================
# Processing Configuration
# ==============================================================================

# Chunk size for processing records
# Match existing pipeline chunk size for consistency
CHUNK_SIZE = 200_000

# Progress bar display
SHOW_PROGRESS = True

# Logging level
LOG_LEVEL = 'INFO'

# ==============================================================================
# Similarity Thresholds (for validation)
# ==============================================================================

# Expected similarity thresholds for validation
# These are heuristics based on empirical observation:
# - Known matches should have similarity > HIGH_SIMILARITY_THRESHOLD
# - Non-matches should have similarity < LOW_SIMILARITY_THRESHOLD

HIGH_SIMILARITY_THRESHOLD = 0.85  # Cosine similarity for likely matches
LOW_SIMILARITY_THRESHOLD = 0.60   # Cosine similarity for likely non-matches

# ==============================================================================
# Version and Metadata
# ==============================================================================

# Model version for tracking
MODEL_VERSION = "v1"

# Metadata keys for embedding storage
METADATA_KEYS = [
    'crefo',          # Business/record identifier
    'index',          # Row index in source data
    'timestamp',      # Generation timestamp
    'model_name',     # Embedding model used
]
