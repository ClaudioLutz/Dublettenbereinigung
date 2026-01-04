# Fix embeddings save memmap file conflict on Windows

## Summary
Fixed an issue where `build_embeddings.py` would fail when saving large datasets because the embeddings file was already open as a memory-mapped file.

## Context / Problem
When processing large datasets (>100K records), `encode_large_dataset()` saves embeddings directly to disk and then loads them back as a read-only memmap. Later, `store.save()` attempted to write to the same file with mode `w+`, causing an `OSError: [Errno 22] Invalid argument` on Windows due to file locking.

This failure occurred after the expensive embedding generation (~1 hour for 7.7M records), causing the FAISS index and metadata to not be saved despite the embeddings being complete.

## What Changed
- **dedupe/ml/embeddings.py**: Added `skip_embeddings` parameter to `EmbeddingStore.save()` method. When `True`, skips re-saving embeddings that were already written externally.
- **scripts/build_embeddings.py**: Added `embeddings_already_saved` flag that tracks whether `encode_large_dataset()` was used. Passes this flag to `store.save()` to avoid the file conflict.
- **scripts/recover_faiss_index.py**: Added recovery script to rebuild FAISS index from existing embeddings (useful for recovering from this failure).

## How to Test
1. Run `python scripts/build_embeddings.py` with a large dataset (>100K records)
2. Verify the script completes without errors
3. Check that all output files exist in `models/embeddings/`:
   - `embeddings_v1.dat`
   - `embeddings_v1_meta.npz`
   - `faiss_index_v1.bin`

## Risk / Rollback Notes
- Low risk change - only affects the save path for large datasets
- Rollback: Revert both file changes; the old behavior will return
- If embeddings were generated but save failed, use `recover_faiss_index.py` to rebuild FAISS index
