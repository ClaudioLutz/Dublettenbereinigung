"""
Embedding generation and storage for ML-based entity matching.

This module provides:
- EmbeddingGenerator: Generate sentence embeddings for address records
- EmbeddingStore: Efficient storage and retrieval of embeddings
- FAISS index management for fast similarity search
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from dedupe.ml.config import (
    BATCH_SIZE,
    DEVICE,
    EMBEDDING_DIM,
    EMBEDDING_DTYPE,
    EMBEDDING_MODEL,
    FAISS_INDEX_TYPE,
    FAISS_N_CLUSTERS,
    FAISS_N_PROBES,
    FAISS_TRAIN_SAMPLE_FRACTION,
    METADATA_KEYS,
    MODEL_VERSION,
    SHOW_PROGRESS,
    TEXT_TEMPLATE,
    TOKEN_ADDR,
    TOKEN_DOB,
    TOKEN_NAME,
    USE_MEMORY_MAPPING,
)

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generate sentence embeddings for address records using sentence-transformers.

    This class wraps a sentence-transformer model and provides utilities for:
    - Text preparation from structured address fields
    - Batch encoding with GPU acceleration
    - Memory-efficient processing of large datasets

    Example:
        >>> generator = EmbeddingGenerator(device='cuda')
        >>> texts = generator.prepare_texts(df, cols)
        >>> embeddings = generator.encode_batch(texts)
    """

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
        device: str = DEVICE,
        batch_size: int = BATCH_SIZE,
        show_progress: bool = SHOW_PROGRESS,
    ):
        """
        Initialize the embedding generator.

        Args:
            model_name: Name of sentence-transformer model to use
            device: 'cuda', 'cpu', or 'auto' (auto-detect GPU)
            batch_size: Number of texts to encode per batch
            show_progress: Whether to show progress bars
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.show_progress = show_progress

        # Auto-detect device
        if device == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device

        logger.info(f"Initializing EmbeddingGenerator with model: {model_name}")
        logger.info(f"Using device: {self.device}")

        # Load model
        self.model = SentenceTransformer(model_name, device=self.device)

        # For memory efficiency on GPU, use half precision
        if self.device == 'cuda':
            self.model.half()
            logger.info("Using fp16 (half precision) on GPU for memory efficiency")

    def prepare_text(
        self,
        first: str = "",
        last: str = "",
        name2: str = "",
        street: str = "",
        house: str = "",
        plz: str = "",
        ort: str = "",
        dob: str = "",
    ) -> str:
        """
        Prepare a single text string from address fields.

        This method concatenates normalized fields with special tokens to help
        the model learn semantic structure.

        Args:
            first: Normalized first name (Vorname)
            last: Normalized last name (Name)
            name2: Normalized second name (Name2)
            street: Normalized street name
            house: Normalized house number
            plz: Postal code (PLZ4)
            ort: Normalized city/locality
            dob: Date of birth (optional)

        Returns:
            Formatted text string for embedding

        Example:
            >>> generator.prepare_text(
            ...     first="hans", last="mueller", street="hauptstrasse",
            ...     house="12", plz="8000", ort="zuerich"
            ... )
            "[NAME] hans mueller [ADDR] hauptstrasse 12 8000 zuerich"
        """
        # Build text using template
        text = TEXT_TEMPLATE.format(
            token_name=TOKEN_NAME,
            first=first or "",
            last=last or "",
            name2=name2 or "",
            token_addr=TOKEN_ADDR,
            street=street or "",
            house=house or "",
            plz=plz or "",
            ort=ort or "",
        )

        # Optionally add DOB
        if dob:
            text += f" {TOKEN_DOB} {dob}"

        # Clean up multiple spaces
        text = " ".join(text.split())

        return text

    def prepare_texts(
        self,
        records: Union[List[Dict], 'pd.DataFrame'],
        field_mapping: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        Prepare a batch of texts from records.

        Args:
            records: List of dictionaries or pandas DataFrame with address fields
            field_mapping: Optional mapping from standard field names to actual column names
                          Default: {'first': 'first', 'last': 'last', ...}

        Returns:
            List of formatted text strings
        """
        # Default field mapping
        if field_mapping is None:
            field_mapping = {
                'first': 'first',
                'last': 'last',
                'name2': 'name2',
                'street': 'street',
                'house': 'house',
                'plz': 'plz4_used',  # Use 4-digit PLZ
                'ort': 'ort',
            }

        texts = []

        # Handle DataFrame
        try:
            import pandas as pd
            if isinstance(records, pd.DataFrame):
                for _, row in records.iterrows():
                    text = self.prepare_text(
                        first=str(row.get(field_mapping['first'], '')),
                        last=str(row.get(field_mapping['last'], '')),
                        name2=str(row.get(field_mapping.get('name2', 'name2'), '')),
                        street=str(row.get(field_mapping['street'], '')),
                        house=str(row.get(field_mapping['house'], '')),
                        plz=str(row.get(field_mapping['plz'], '')),
                        ort=str(row.get(field_mapping['ort'], '')),
                    )
                    texts.append(text)
                return texts
        except ImportError:
            pass

        # Handle list of dicts
        for record in records:
            text = self.prepare_text(
                first=str(record.get(field_mapping['first'], '')),
                last=str(record.get(field_mapping['last'], '')),
                name2=str(record.get(field_mapping.get('name2', 'name2'), '')),
                street=str(record.get(field_mapping['street'], '')),
                house=str(record.get(field_mapping['house'], '')),
                plz=str(record.get(field_mapping['plz'], '')),
                ort=str(record.get(field_mapping['ort'], '')),
            )
            texts.append(text)

        return texts

    def encode_batch(
        self,
        texts: List[str],
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        """
        Encode a batch of texts into embeddings.

        Args:
            texts: List of text strings to encode
            normalize_embeddings: Whether to L2-normalize embeddings
                                 (recommended for cosine similarity)

        Returns:
            Numpy array of shape (len(texts), EMBEDDING_DIM)
        """
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=self.show_progress,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True,
        )

        return embeddings.astype(EMBEDDING_DTYPE)

    def encode_large_dataset(
        self,
        texts: List[str],
        output_path: Union[str, Path],
        chunk_size: int = 10000,
    ) -> None:
        """
        Encode a large dataset in chunks, writing to memory-mapped file.

        This method is memory-efficient for very large datasets (millions of records).

        Args:
            texts: List of all texts to encode
            output_path: Path to output .dat file for memory-mapped embeddings
            chunk_size: Number of texts to process at once
        """
        n_texts = len(texts)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create memory-mapped array
        embeddings = np.memmap(
            output_path,
            dtype=EMBEDDING_DTYPE,
            mode='w+',
            shape=(n_texts, EMBEDDING_DIM),
        )

        logger.info(f"Encoding {n_texts} texts in chunks of {chunk_size}")

        # Process in chunks
        for start_idx in tqdm(
            range(0, n_texts, chunk_size),
            desc="Encoding chunks",
            disable=not self.show_progress,
        ):
            end_idx = min(start_idx + chunk_size, n_texts)
            chunk_texts = texts[start_idx:end_idx]

            # Encode chunk
            chunk_embeddings = self.encode_batch(chunk_texts)

            # Write to memory-mapped array
            embeddings[start_idx:end_idx] = chunk_embeddings

            # Flush to disk
            embeddings.flush()

            # Clear GPU cache if using CUDA
            if self.device == 'cuda':
                torch.cuda.empty_cache()

        logger.info(f"Embeddings saved to {output_path}")


class EmbeddingStore:
    """
    Efficient storage and retrieval of embeddings with FAISS indexing.

    This class manages:
    - Memory-mapped embedding storage
    - Metadata (Crefo IDs, row indices)
    - FAISS index for fast nearest-neighbor search
    - Cosine similarity computation

    Example:
        >>> store = EmbeddingStore.load('models/embeddings')
        >>> emb_a = store.lookup(100)
        >>> emb_b = store.lookup(200)
        >>> similarity = store.get_similarity(100, 200)
    """

    def __init__(
        self,
        embeddings: np.ndarray,
        metadata: Dict[str, np.ndarray],
        faiss_index: Optional['faiss.Index'] = None,
    ):
        """
        Initialize the embedding store.

        Args:
            embeddings: Numpy array of embeddings (n_records, embedding_dim)
            metadata: Dictionary with metadata arrays (crefo, index, etc.)
            faiss_index: Optional FAISS index for fast search
        """
        self.embeddings = embeddings
        self.metadata = metadata
        self.faiss_index = faiss_index

        # Build index mappings
        self._build_index_mappings()

    def _build_index_mappings(self):
        """Build fast lookup mappings from Crefo/index to embedding position."""
        self.crefo_to_pos = {}
        self.index_to_pos = {}

        if 'crefo' in self.metadata:
            for pos, crefo in enumerate(self.metadata['crefo']):
                if crefo:  # Skip empty/null Crefo values
                    self.crefo_to_pos[crefo] = pos

        if 'index' in self.metadata:
            for pos, idx in enumerate(self.metadata['index']):
                self.index_to_pos[idx] = pos

    def lookup(self, position: int) -> np.ndarray:
        """
        Retrieve embedding by position.

        Args:
            position: Position in embedding array

        Returns:
            Embedding vector (embedding_dim,)
        """
        return self.embeddings[position]

    def lookup_by_crefo(self, crefo: str) -> Optional[np.ndarray]:
        """
        Retrieve embedding by Crefo ID.

        Args:
            crefo: Crefo identifier

        Returns:
            Embedding vector or None if not found
        """
        pos = self.crefo_to_pos.get(crefo)
        if pos is not None:
            return self.embeddings[pos]
        return None

    def lookup_by_index(self, index: int) -> Optional[np.ndarray]:
        """
        Retrieve embedding by row index.

        Args:
            index: Row index in source data

        Returns:
            Embedding vector or None if not found
        """
        pos = self.index_to_pos.get(index)
        if pos is not None:
            return self.embeddings[pos]
        return None

    def lookup_batch(self, positions: List[int]) -> np.ndarray:
        """
        Retrieve multiple embeddings by position.

        Args:
            positions: List of positions

        Returns:
            Array of embeddings (len(positions), embedding_dim)
        """
        return self.embeddings[positions]

    def get_similarity(
        self,
        pos_a: int,
        pos_b: int,
        metric: str = 'cosine',
    ) -> float:
        """
        Compute similarity between two embeddings.

        Args:
            pos_a: Position of first embedding
            pos_b: Position of second embedding
            metric: Similarity metric ('cosine' or 'euclidean')

        Returns:
            Similarity score
        """
        emb_a = self.embeddings[pos_a]
        emb_b = self.embeddings[pos_b]

        if metric == 'cosine':
            # Cosine similarity (assumes normalized embeddings)
            return float(np.dot(emb_a, emb_b))
        elif metric == 'euclidean':
            # Euclidean distance (lower is more similar)
            return float(np.linalg.norm(emb_a - emb_b))
        else:
            raise ValueError(f"Unknown metric: {metric}")

    def search_similar(
        self,
        query_position: int,
        k: int = 10,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find k nearest neighbors using FAISS index.

        Args:
            query_position: Position of query embedding
            k: Number of neighbors to return

        Returns:
            Tuple of (distances, indices) for k nearest neighbors
        """
        if self.faiss_index is None:
            raise RuntimeError("FAISS index not built. Call build_faiss_index() first.")

        query_embedding = self.embeddings[query_position:query_position+1]
        distances, indices = self.faiss_index.search(query_embedding, k)

        return distances[0], indices[0]

    def build_faiss_index(
        self,
        index_type: str = FAISS_INDEX_TYPE,
        n_clusters: int = FAISS_N_CLUSTERS,
        n_probes: int = FAISS_N_PROBES,
        train_sample_fraction: float = FAISS_TRAIN_SAMPLE_FRACTION,
    ):
        """
        Build FAISS index for fast similarity search.

        Args:
            index_type: Type of index ('IVF' or 'Flat')
            n_clusters: Number of clusters for IVF index
            n_probes: Number of clusters to probe during search
            train_sample_fraction: Fraction of data to use for training
        """
        try:
            import faiss
        except ImportError:
            logger.error("FAISS not installed. Install with: pip install faiss-cpu")
            raise

        logger.info(f"Building FAISS {index_type} index with {n_clusters} clusters")

        n_embeddings = len(self.embeddings)

        if index_type == 'IVF':
            # Create IVF index with flat quantization
            quantizer = faiss.IndexFlatL2(EMBEDDING_DIM)
            self.faiss_index = faiss.IndexIVFFlat(
                quantizer,
                EMBEDDING_DIM,
                n_clusters,
                faiss.METRIC_L2,
            )

            # Train on sample
            train_size = int(n_embeddings * train_sample_fraction)
            train_indices = np.random.choice(n_embeddings, train_size, replace=False)
            train_data = self.embeddings[train_indices]

            logger.info(f"Training index on {train_size} samples")
            self.faiss_index.train(train_data)

            # Set number of probes
            self.faiss_index.nprobe = n_probes

        elif index_type == 'Flat':
            # Simple flat index (exact search, slower but accurate)
            self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIM)

        else:
            raise ValueError(f"Unknown index type: {index_type}")

        # Add all embeddings
        logger.info(f"Adding {n_embeddings} embeddings to index")
        self.faiss_index.add(self.embeddings)

        logger.info("FAISS index built successfully")

    def save(self, output_dir: Union[str, Path]):
        """
        Save embedding store to disk.

        Args:
            output_dir: Directory to save embeddings and metadata
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save embeddings
        embeddings_path = output_dir / f"embeddings_{MODEL_VERSION}.dat"
        if USE_MEMORY_MAPPING:
            # Create memory-mapped file
            mmap_embeddings = np.memmap(
                embeddings_path,
                dtype=EMBEDDING_DTYPE,
                mode='w+',
                shape=self.embeddings.shape,
            )
            mmap_embeddings[:] = self.embeddings[:]
            mmap_embeddings.flush()
        else:
            np.save(embeddings_path, self.embeddings)

        # Save metadata
        metadata_path = output_dir / f"embeddings_{MODEL_VERSION}_meta.npz"
        np.savez(metadata_path, **self.metadata)

        # Save FAISS index
        if self.faiss_index is not None:
            try:
                import faiss
                index_path = output_dir / f"faiss_index_{MODEL_VERSION}.bin"
                faiss.write_index(self.faiss_index, str(index_path))
                logger.info(f"FAISS index saved to {index_path}")
            except ImportError:
                logger.warning("FAISS not installed, skipping index save")

        logger.info(f"Embedding store saved to {output_dir}")

    @classmethod
    def load(cls, input_dir: Union[str, Path]) -> 'EmbeddingStore':
        """
        Load embedding store from disk.

        Args:
            input_dir: Directory containing embeddings and metadata

        Returns:
            EmbeddingStore instance
        """
        input_dir = Path(input_dir)

        # Load embeddings
        embeddings_path = input_dir / f"embeddings_{MODEL_VERSION}.dat"
        if embeddings_path.exists():
            if USE_MEMORY_MAPPING:
                # Determine shape from metadata first
                metadata_path = input_dir / f"embeddings_{MODEL_VERSION}_meta.npz"
                if metadata_path.exists():
                    meta_data = np.load(metadata_path, allow_pickle=True)
                    n_records = len(meta_data['index']) if 'index' in meta_data else 0
                    embeddings = np.memmap(
                        embeddings_path,
                        dtype=EMBEDDING_DTYPE,
                        mode='r',
                        shape=(n_records, EMBEDDING_DIM),
                    )
                else:
                    raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
            else:
                embeddings = np.load(embeddings_path)
        else:
            raise FileNotFoundError(f"Embeddings file not found: {embeddings_path}")

        # Load metadata
        metadata_path = input_dir / f"embeddings_{MODEL_VERSION}_meta.npz"
        if metadata_path.exists():
            metadata = dict(np.load(metadata_path, allow_pickle=True))
        else:
            metadata = {}

        # Load FAISS index
        faiss_index = None
        index_path = input_dir / f"faiss_index_{MODEL_VERSION}.bin"
        if index_path.exists():
            try:
                import faiss
                faiss_index = faiss.read_index(str(index_path))
                logger.info(f"FAISS index loaded from {index_path}")
            except ImportError:
                logger.warning("FAISS not installed, index not loaded")

        logger.info(f"Embedding store loaded from {input_dir}")

        return cls(embeddings, metadata, faiss_index)
