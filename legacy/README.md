# Legacy Implementations

This folder contains previous implementations of the duplicate checker that are no longer actively used but preserved for reference.

## Files

### duplicate_checker_poc.py

**Status:** Reference Implementation (Proof of Concept)

The original proof-of-concept implementation that established the business rules and matching logic. This file is preserved as a reference for understanding the original design decisions and business logic.

**Key Features:**
- Original business rules implementation
- Basic blocking strategy
- Confidence scoring logic

**Note:** This implementation is not optimized for performance. For production use, see `duplicate_checker_optimized.py` in the root directory.

**Referenced By:**
- `docs/businessrules.md` (as business logic reference)
- Various story documentation

### duplicate_checker_integration.py

**Status:** Legacy Integration Layer

An older integration layer that wrapped the POC checker. This file used the POC implementation and had parallel processing disabled due to serialization issues (resolved in the optimized version).

**Why Deprecated:**
- Used POC implementation instead of optimized version
- Had parallel processing disabled
- Contained hard-coded debug output
- Not part of recommended workflow

**Superseded By:** `run_optimized_analysis.py` + `duplicate_checker_optimized.py`

## Active Codebase

For the current, production-ready implementation, use:

- **Main Entry Point:** `run_optimized_analysis.py`
- **Production Engine:** `duplicate_checker_optimized.py`
- **Documentation:** `QUICK_START.md`, `README_OPTIMIZATION.md`

## Migration Notes

If you have scripts or tools that reference the legacy implementations:

1. **Replace `duplicate_checker_integration.py` imports:**
   ```python
   # OLD
   from duplicate_checker_integration import DuplicateChecker

   # NEW
   from duplicate_checker_optimized import UltraFastDuplicateChecker
   ```

2. **Update method calls:**
   ```python
   # OLD
   checker = DuplicateChecker()
   results = checker.analyze_duplicates(df)

   # NEW
   checker = UltraFastDuplicateChecker(
       fuzzy_threshold=0.7,
       use_phonetic=True,
       max_workers=4
   )
   results = checker.analyze_duplicates(df, confidence_threshold=70.0)
   ```

3. **Update configuration:**
   - The optimized version uses different parameter names and defaults
   - See `QUICK_START.md` for complete examples

## Questions?

For questions about the active codebase, see:
- `QUICK_START.md` - Quick start guide
- `README_OPTIMIZATION.md` - Optimization details
- `docs/ARCHITECTURE.md` - Architecture overview

---

**Last Updated:** 2025-12-17
