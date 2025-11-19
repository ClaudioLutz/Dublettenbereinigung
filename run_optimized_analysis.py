"""
Integration Script for Ultra-Fast Duplicate Checker with SQL Server
====================================================================

This script integrates the optimized duplicate checker with your existing
data.py SQL Server connection to process the full 7.5M records.

Usage:
    python run_optimized_analysis.py [--limit LIMIT] [--confidence THRESHOLD]
"""

import argparse
import time
import logging
from duplicate_checker_optimized import UltraFastDuplicateChecker, benchmark_performance
from data import lade_daten, engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Run optimized duplicate analysis')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of records to process (None = all)')
    parser.add_argument('--confidence', type=float, default=70.0,
                       help='Confidence threshold (default: 70.0)')
    parser.add_argument('--fuzzy-threshold', type=float, default=0.7,
                       help='Fuzzy match threshold (default: 0.7)')
    parser.add_argument('--no-parallel', action='store_true',
                       help='Disable parallel processing')
    parser.add_argument('--benchmark', action='store_true',
                       help='Run performance benchmark before full analysis')
    parser.add_argument('--output', type=str, default='duplicates_results.csv',
                       help='Output filename (default: duplicates_results.csv)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("ULTRA-FAST DUPLICATE CHECKER - SQL Server Integration")
    print("=" * 80)
    print()
    
    # Load data from SQL Server
    logger.info(f"Loading data from SQL Server (limit: {args.limit or 'ALL'})")
    start_load = time.time()
    
    try:
        # Build query with dynamic TOP clause
        if args.limit:
            top_clause = f"TOP ({args.limit})"
        else:
            top_clause = ""
        
        query = f"""
        SELECT {top_clause} [Name]
              ,[Vorname]
              ,[Name2]
              ,[Strasse]
              ,[HausNummer]
              ,[Plz]
              ,[Ort]
              ,[Crefo]
              ,[Geburtstag]
              ,[Jahrgang]
              ,[Erfasst]
              ,[Quelle_95]
          FROM [CAG_Analyse].[dbo].[vAdresse_Quelle95]
          WHERE Erfasst < dateadd(day,-7,getdate())
        """
        
        df = lade_daten(engine, query)
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return 1
    
    load_time = time.time() - start_load
    logger.info(f"Loaded {len(df):,} records in {load_time:.2f}s")
    
    if len(df) == 0:
        logger.error("No data loaded!")
        return 1
    
    print()
    print(f"Dataset size: {len(df):,} records")
    print(f"Confidence threshold: {args.confidence}%")
    print(f"Fuzzy threshold: {args.fuzzy_threshold}")
    print(f"Parallel processing: {'disabled' if args.no_parallel else 'enabled'}")
    print()
    
    # Run benchmark if requested
    if args.benchmark and len(df) >= 10000:
        print("\n--- Running Performance Benchmark ---")
        # Determine sensible benchmark sizes based on dataset
        if len(df) >= 1_000_000:
            sizes = [10000, 100000, 500000]
        elif len(df) >= 100000:
            sizes = [1000, 10000, 50000]
        else:
            sizes = [1000, min(10000, len(df)//2)]
        
        benchmark_performance(df, sample_sizes=sizes)
        print()
        
        response = input("\nContinue with full analysis? (y/n): ")
        if response.lower() != 'y':
            print("Analysis cancelled.")
            return 0
        print()
    
    # Initialize checker
    checker = UltraFastDuplicateChecker(
        fuzzy_threshold=args.fuzzy_threshold,
        use_parallel=not args.no_parallel
    )
    
    # Run analysis
    print("=" * 80)
    print("STARTING DUPLICATE ANALYSIS")
    print("=" * 80)
    print()
    
    start_analysis = time.time()
    
    try:
        matches = checker.analyze_duplicates(df, confidence_threshold=args.confidence)
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return 1
    
    analysis_time = time.time() - start_analysis
    
    # Print results summary
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print(f"Total records analyzed:  {len(df):,}")
    print(f"Total matches found:     {len(matches):,}")
    print(f"Processing time:         {analysis_time:.2f}s ({analysis_time/60:.1f} min)")
    print(f"Processing rate:         {len(df)/analysis_time:,.0f} records/second")
    print()
    
    if matches:
        # Match type breakdown
        exact = sum(1 for m in matches if m.match_type == 'exact')
        fuzzy_normal = sum(1 for m in matches if m.match_type == 'fuzzy_normal')
        fuzzy_swapped = sum(1 for m in matches if m.match_type == 'fuzzy_swapped')
        
        print("Match type breakdown:")
        print(f"  Exact matches:        {exact:,}")
        print(f"  Fuzzy matches:        {fuzzy_normal:,}")
        print(f"  Swapped name matches: {fuzzy_swapped:,}")
        print()
        
        # Confidence distribution
        high_conf = sum(1 for m in matches if m.confidence_score >= 90)
        med_conf = sum(1 for m in matches if 80 <= m.confidence_score < 90)
        low_conf = sum(1 for m in matches if m.confidence_score < 80)
        
        avg_conf = sum(m.confidence_score for m in matches) / len(matches)
        
        print("Confidence distribution:")
        print(f"  High (≥90%):  {high_conf:,}")
        print(f"  Medium (80-89%): {med_conf:,}")
        print(f"  Low (<80%):   {low_conf:,}")
        print(f"  Average:      {avg_conf:.1f}%")
        print()
        
        # Export results
        print(f"Exporting results to '{args.output}'...")
        start_export = time.time()
        
        try:
            checker.export_results(matches, df, args.output)
            export_time = time.time() - start_export
            print(f"Export complete in {export_time:.2f}s")
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return 1
    else:
        print("No duplicates found.")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total execution time: {time.time() - start_load:.2f}s")
    print(f"  - Data loading:     {load_time:.2f}s")
    print(f"  - Analysis:         {analysis_time:.2f}s")
    if matches:
        print(f"  - Export:           {export_time:.2f}s")
    print()
    
    return 0

if __name__ == "__main__":
    exit(main())
