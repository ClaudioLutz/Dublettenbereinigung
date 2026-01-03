"""
Unit tests for ML embeddings module.

Tests cover:
- EmbeddingGenerator text preparation
- EmbeddingGenerator encoding
- EmbeddingStore storage and retrieval
- EmbeddingStore similarity computation
- EmbeddingStore save/load functionality
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from dedupe.ml.config import EMBEDDING_DIM
from dedupe.ml.embeddings import EmbeddingGenerator, EmbeddingStore


class TestEmbeddingGenerator:
    """Tests for EmbeddingGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create an embedding generator instance for testing."""
        # Use CPU for testing to avoid GPU dependency
        return EmbeddingGenerator(device='cpu', batch_size=4, show_progress=False)

    def test_prepare_text_basic(self, generator):
        """Test basic text preparation."""
        text = generator.prepare_text(
            first="hans",
            last="mueller",
            street="hauptstrasse",
            house="12",
            plz="8000",
            ort="zuerich",
        )

        assert "[NAME]" in text
        assert "[ADDR]" in text
        assert "hans" in text
        assert "mueller" in text
        assert "hauptstrasse" in text
        assert "12" in text
        assert "8000" in text
        assert "zuerich" in text

    def test_prepare_text_with_name2(self, generator):
        """Test text preparation with second name."""
        text = generator.prepare_text(
            first="maria",
            last="mueller",
            name2="schmidt",
            street="bahnhofstrasse",
            house="5a",
            plz="3000",
            ort="bern",
        )

        assert "maria" in text
        assert "mueller" in text
        assert "schmidt" in text  # name2 should be included
        assert "bahnhofstrasse" in text

    def test_prepare_text_empty_fields(self, generator):
        """Test text preparation with empty fields."""
        text = generator.prepare_text(
            first="",
            last="mueller",
            street="",
            house="",
            plz="8000",
            ort="",
        )

        # Should handle empty fields gracefully
        assert "[NAME]" in text
        assert "[ADDR]" in text
        assert "mueller" in text
        assert "8000" in text

        # Should not have multiple consecutive spaces
        assert "  " not in text

    def test_prepare_text_special_characters(self, generator):
        """Test text preparation with German umlauts."""
        text = generator.prepare_text(
            first="hans",
            last="müller",  # Umlaut
            street="zürichstrasse",  # Umlaut
            house="10",
            plz="8000",
            ort="zürich",  # Umlaut
        )

        # Should preserve umlauts (normalized in preprocessing, not here)
        assert "müller" in text
        assert "zürich" in text

    def test_encode_batch_basic(self, generator):
        """Test basic batch encoding."""
        texts = [
            "[NAME] hans mueller [ADDR] hauptstrasse 12 8000 zuerich",
            "[NAME] maria schmidt [ADDR] bahnhofstrasse 5 3000 bern",
        ]

        embeddings = generator.encode_batch(texts)

        # Check shape
        assert embeddings.shape == (2, EMBEDDING_DIM)

        # Check dtype
        assert embeddings.dtype == np.float32

        # Check normalization (embeddings should be L2-normalized)
        for i in range(len(embeddings)):
            norm = np.linalg.norm(embeddings[i])
            assert np.isclose(norm, 1.0, atol=1e-5), f"Embedding {i} not normalized: norm={norm}"

    def test_encode_batch_similar_texts(self, generator):
        """Test that similar texts produce similar embeddings."""
        texts = [
            "[NAME] hans mueller [ADDR] hauptstrasse 12 8000 zuerich",
            "[NAME] hans müller [ADDR] hauptstrasse 12 8000 zuerich",  # Very similar
            "[NAME] maria schmidt [ADDR] bahnhofstrasse 5 3000 bern",  # Different
        ]

        embeddings = generator.encode_batch(texts)

        # Compute cosine similarities
        sim_0_1 = np.dot(embeddings[0], embeddings[1])  # Similar
        sim_0_2 = np.dot(embeddings[0], embeddings[2])  # Different

        # Similar texts should have higher similarity
        assert sim_0_1 > sim_0_2
        assert sim_0_1 > 0.85  # Should be very similar

    def test_encode_batch_empty_text(self, generator):
        """Test encoding with empty or whitespace-only text."""
        texts = [
            "[NAME] hans mueller [ADDR] hauptstrasse 12 8000 zuerich",
            "",  # Empty
            "   ",  # Whitespace only
        ]

        embeddings = generator.encode_batch(texts)

        # Should still produce valid embeddings
        assert embeddings.shape == (3, EMBEDDING_DIM)
        assert not np.isnan(embeddings).any()


class TestEmbeddingStore:
    """Tests for EmbeddingStore class."""

    @pytest.fixture
    def sample_store(self):
        """Create a sample embedding store for testing."""
        # Create sample embeddings
        embeddings = np.random.randn(100, EMBEDDING_DIM).astype(np.float32)

        # Normalize embeddings
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        # Create sample metadata
        metadata = {
            'crefo': np.array([f'CREFO{i:04d}' for i in range(100)]),
            'index': np.arange(100),
        }

        return EmbeddingStore(embeddings, metadata, faiss_index=None)

    def test_lookup_by_position(self, sample_store):
        """Test embedding lookup by position."""
        emb = sample_store.lookup(0)

        assert emb.shape == (EMBEDDING_DIM,)
        assert np.isclose(np.linalg.norm(emb), 1.0, atol=1e-5)  # Normalized

    def test_lookup_by_crefo(self, sample_store):
        """Test embedding lookup by Crefo ID."""
        emb = sample_store.lookup_by_crefo('CREFO0010')

        assert emb is not None
        assert emb.shape == (EMBEDDING_DIM,)

        # Non-existent Crefo should return None
        emb_missing = sample_store.lookup_by_crefo('CREFO9999')
        assert emb_missing is None

    def test_lookup_by_index(self, sample_store):
        """Test embedding lookup by row index."""
        emb = sample_store.lookup_by_index(50)

        assert emb is not None
        assert emb.shape == (EMBEDDING_DIM,)

    def test_lookup_batch(self, sample_store):
        """Test batch embedding lookup."""
        positions = [0, 10, 20, 30]
        embeddings = sample_store.lookup_batch(positions)

        assert embeddings.shape == (4, EMBEDDING_DIM)

    def test_get_similarity_cosine(self, sample_store):
        """Test cosine similarity computation."""
        # Similarity with self should be 1.0
        sim_self = sample_store.get_similarity(0, 0, metric='cosine')
        assert np.isclose(sim_self, 1.0, atol=1e-5)

        # Similarity with others should be < 1.0
        sim_other = sample_store.get_similarity(0, 1, metric='cosine')
        assert sim_other < 1.0
        assert sim_other > -1.0  # Cosine similarity is in [-1, 1]

    def test_get_similarity_euclidean(self, sample_store):
        """Test Euclidean distance computation."""
        # Distance to self should be 0
        dist_self = sample_store.get_similarity(0, 0, metric='euclidean')
        assert np.isclose(dist_self, 0.0, atol=1e-5)

        # Distance to others should be > 0
        dist_other = sample_store.get_similarity(0, 1, metric='euclidean')
        assert dist_other > 0

    def test_get_similarity_symmetry(self, sample_store):
        """Test that similarity is symmetric."""
        sim_ab = sample_store.get_similarity(10, 20, metric='cosine')
        sim_ba = sample_store.get_similarity(20, 10, metric='cosine')

        assert np.isclose(sim_ab, sim_ba, atol=1e-6)

    def test_save_and_load(self, sample_store):
        """Test saving and loading embedding store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save
            sample_store.save(tmpdir)

            # Check files exist
            tmpdir_path = Path(tmpdir)
            assert (tmpdir_path / "embeddings_v1.dat").exists()
            assert (tmpdir_path / "embeddings_v1_meta.npz").exists()

            # Load
            loaded_store = EmbeddingStore.load(tmpdir)

            # Verify embeddings match
            np.testing.assert_array_almost_equal(
                sample_store.embeddings,
                loaded_store.embeddings,
            )

            # Verify metadata matches
            np.testing.assert_array_equal(
                sample_store.metadata['crefo'],
                loaded_store.metadata['crefo'],
            )
            np.testing.assert_array_equal(
                sample_store.metadata['index'],
                loaded_store.metadata['index'],
            )

    def test_build_faiss_index(self, sample_store):
        """Test FAISS index building."""
        pytest.importorskip("faiss")  # Skip if FAISS not installed

        # Build index
        sample_store.build_faiss_index(
            index_type='IVF',
            n_clusters=10,  # Small number for testing
            train_sample_fraction=0.5,
        )

        assert sample_store.faiss_index is not None

    def test_search_similar(self, sample_store):
        """Test nearest neighbor search with FAISS."""
        pytest.importorskip("faiss")  # Skip if FAISS not installed

        # Build index
        sample_store.build_faiss_index(
            index_type='Flat',  # Use flat index for exact results
        )

        # Search for nearest neighbors
        distances, indices = sample_store.search_similar(0, k=5)

        # First result should be the query itself
        assert indices[0] == 0
        assert np.isclose(distances[0], 0.0, atol=1e-5)

        # Should return 5 results
        assert len(indices) == 5
        assert len(distances) == 5


class TestEmbeddingIntegration:
    """Integration tests combining generator and store."""

    def test_generate_and_store_workflow(self):
        """Test complete workflow: generate embeddings and store them."""
        # Create generator
        generator = EmbeddingGenerator(device='cpu', show_progress=False)

        # Prepare texts
        texts = [
            generator.prepare_text(
                first="hans", last="mueller",
                street="hauptstrasse", house="12",
                plz="8000", ort="zuerich"
            ),
            generator.prepare_text(
                first="maria", last="schmidt",
                street="bahnhofstrasse", house="5",
                plz="3000", ort="bern"
            ),
            generator.prepare_text(
                first="peter", last="weber",
                street="dorfstrasse", house="1",
                plz="4000", ort="basel"
            ),
        ]

        # Generate embeddings
        embeddings = generator.encode_batch(texts)

        # Create metadata
        metadata = {
            'crefo': np.array(['CREFO001', 'CREFO002', 'CREFO003']),
            'index': np.array([0, 1, 2]),
        }

        # Create store
        store = EmbeddingStore(embeddings, metadata)

        # Test lookups
        assert store.lookup_by_crefo('CREFO001') is not None
        assert store.lookup_by_index(1) is not None

        # Test similarity
        sim = store.get_similarity(0, 1, metric='cosine')
        assert 0 <= sim <= 1

    def test_save_load_roundtrip(self):
        """Test that save/load preserves all data."""
        # Generate test data
        generator = EmbeddingGenerator(device='cpu', show_progress=False)

        texts = [
            generator.prepare_text(first="test1", last="user1", street="street1", plz="1000"),
            generator.prepare_text(first="test2", last="user2", street="street2", plz="2000"),
        ]

        embeddings = generator.encode_batch(texts)
        metadata = {
            'crefo': np.array(['A', 'B']),
            'index': np.array([0, 1]),
        }

        original_store = EmbeddingStore(embeddings, metadata)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save
            original_store.save(tmpdir)

            # Load
            loaded_store = EmbeddingStore.load(tmpdir)

            # Compare embeddings
            np.testing.assert_array_almost_equal(
                original_store.embeddings,
                loaded_store.embeddings,
            )

            # Compare similarity results
            sim_original = original_store.get_similarity(0, 1)
            sim_loaded = loaded_store.get_similarity(0, 1)
            assert np.isclose(sim_original, sim_loaded)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
