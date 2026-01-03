"""
ML Setup Verification Script

This script verifies that all ML dependencies and infrastructure are properly installed
and configured before running the ML-based entity matching pipeline.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_check(name, status, details=""):
    """Print a check result."""
    icon = "✅" if status else "❌"
    print(f"{icon} {name}", end="")
    if details:
        print(f" - {details}")
    else:
        print()

def check_python_version():
    """Check Python version."""
    print_header("Python Version")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print(f"Python version: {version_str}")
    
    is_ok = version.major == 3 and version.minor >= 9
    print_check("Python 3.9+", is_ok, f"{'OK' if is_ok else 'Need 3.9+'}")
    return is_ok

def check_core_dependencies():
    """Check core Python dependencies."""
    print_header("Core Dependencies")
    
    dependencies = {
        'pandas': 'pandas',
        'numpy': 'numpy',
        'sqlalchemy': 'sqlalchemy',
        'pyodbc': 'pyodbc',
    }
    
    all_ok = True
    for name, import_name in dependencies.items():
        try:
            module = __import__(import_name)
            version = getattr(module, '__version__', 'unknown')
            print_check(name, True, f"v{version}")
        except ImportError as e:
            print_check(name, False, f"Not installed")
            all_ok = False
    
    return all_ok

def check_ml_dependencies():
    """Check ML-specific dependencies."""
    print_header("ML Dependencies")
    
    ml_deps = {
        'torch': 'PyTorch',
        'sentence_transformers': 'Sentence Transformers',
        'lightgbm': 'LightGBM',
        'faiss': 'FAISS',
        'sklearn': 'scikit-learn',
        'numba': 'Numba',
        'joblib': 'Joblib',
    }
    
    all_ok = True
    for import_name, display_name in ml_deps.items():
        try:
            module = __import__(import_name)
            version = getattr(module, '__version__', 'unknown')
            print_check(display_name, True, f"v{version}")
        except ImportError:
            print_check(display_name, False, "Not installed")
            all_ok = False
    
    return all_ok

def check_gpu():
    """Check GPU availability and configuration."""
    print_header("GPU Configuration")
    
    try:
        import torch
        
        cuda_available = torch.cuda.is_available()
        print_check("CUDA Available", cuda_available)
        
        if cuda_available:
            device_count = torch.cuda.device_count()
            print(f"   GPU Count: {device_count}")
            
            for i in range(device_count):
                device_name = torch.cuda.get_device_name(i)
                print(f"   GPU {i}: {device_name}")
            
            # Check CUDA version
            cuda_version = torch.version.cuda
            print(f"   CUDA Version: {cuda_version}")
            
            # Check PyTorch version
            pytorch_version = torch.__version__
            print(f"   PyTorch Version: {pytorch_version}")
            
            return True
        else:
            print("   ℹ️  GPU not available - will use CPU (slower)")
            return True  # Not a failure, just slower
            
    except Exception as e:
        print_check("GPU Check", False, f"Error: {e}")
        return False

def check_file_structure():
    """Check that required directories and files exist."""
    print_header("File Structure")
    
    required_paths = [
        ('dedupe/ml/', 'ML Module'),
        ('dedupe/ml_training/', 'ML Training Module'),
        ('scripts/build_embeddings.py', 'Embeddings Script'),
        ('scripts/train_ml_model.py', 'Training Script'),
        ('scripts/run_dedupe.py', 'Deduplication Script'),
        ('scripts/generate_silver_labels.py', 'Silver Labels Script'),
        ('requirements.txt', 'Requirements File'),
        ('query.sql', 'Query File'),
    ]
    
    all_ok = True
    for path_str, description in required_paths:
        path = Path(path_str)
        exists = path.exists()
        print_check(description, exists, path_str)
        if not exists:
            all_ok = False
    
    return all_ok

def check_ml_modules():
    """Check that ML modules can be imported."""
    print_header("ML Module Imports")
    
    modules = [
        'dedupe.ml.config',
        'dedupe.ml.embeddings',
        'dedupe.ml.features',
        'dedupe.ml.model',
        'dedupe.ml.scoring_ml',
        'dedupe.ml.calibration',
        'dedupe.ml_training.silver_labels',
        'dedupe.ml_training.train',
    ]
    
    all_ok = True
    for module_name in modules:
        try:
            __import__(module_name)
            print_check(module_name, True)
        except ImportError as e:
            print_check(module_name, False, f"Import error: {e}")
            all_ok = False
        except Exception as e:
            print_check(module_name, False, f"Error: {e}")
            all_ok = False
    
    return all_ok

def check_directory_writable():
    """Check that output directories can be created."""
    print_header("Directory Permissions")
    
    test_dirs = [
        'models',
        'models/embeddings',
        'models/lightgbm',
    ]
    
    all_ok = True
    for dir_path in test_dirs:
        path = Path(dir_path)
        try:
            path.mkdir(parents=True, exist_ok=True)
            print_check(f"Can create {dir_path}", True)
        except Exception as e:
            print_check(f"Can create {dir_path}", False, f"Error: {e}")
            all_ok = False
    
    return all_ok

def check_database_connection(check_db=False):
    """Optionally check database connectivity."""
    if not check_db:
        return True
    
    print_header("Database Connection (Optional)")
    
    try:
        import os
        from sqlalchemy import create_engine
        
        server = os.getenv('DEDUPE_DB_SERVER')
        database = os.getenv('DEDUPE_DB_DATABASE')
        
        if not server or not database:
            print("   ℹ️  Database environment variables not set")
            print("   Set DEDUPE_DB_SERVER and DEDUPE_DB_DATABASE to test connection")
            return True
        
        print(f"   Server: {server}")
        print(f"   Database: {database}")
        
        connection_string = f"mssql+pyodbc://{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
        engine = create_engine(connection_string)
        
        with engine.connect() as conn:
            result = conn.execute("SELECT 1").scalar()
            print_check("Database Connection", result == 1)
            return True
            
    except Exception as e:
        print_check("Database Connection", False, f"Error: {e}")
        print("   ℹ️  Database connection not required for verification")
        return True  # Don't fail verification on DB issues

def print_summary(checks):
    """Print summary of all checks."""
    print_header("Summary")
    
    total = len(checks)
    passed = sum(1 for status in checks.values() if status)
    
    print(f"\nTotal Checks: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    
    if passed == total:
        print("\n🎉 All checks passed! Your ML setup is ready.")
        print("\n📖 Next Steps:")
        print("   1. Read GETTING_STARTED_ML.md for usage instructions")
        print("   2. Start with Phase 1: Generate embeddings")
        print("   3. Or test on small dataset first (recommended)")
        return True
    else:
        print("\n⚠️  Some checks failed. Please review the errors above.")
        print("\n💡 Common Fixes:")
        print("   - Install missing dependencies: pip install -r requirements.txt")
        print("   - Ensure virtual environment is activated")
        print("   - Check CUDA drivers if GPU checks failed")
        return False

def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("  ML Setup Verification")
    print("  Checking your environment for ML-based entity matching")
    print("=" * 70)
    
    checks = {}
    
    # Run all checks
    checks['Python Version'] = check_python_version()
    checks['Core Dependencies'] = check_core_dependencies()
    checks['ML Dependencies'] = check_ml_dependencies()
    checks['GPU Configuration'] = check_gpu()
    checks['File Structure'] = check_file_structure()
    checks['ML Modules'] = check_ml_modules()
    checks['Directory Permissions'] = check_directory_writable()
    
    # Optional DB check
    import sys
    check_db = '--check-db' in sys.argv
    if check_db:
        checks['Database Connection'] = check_database_connection(check_db=True)
    
    # Print summary
    success = print_summary(checks)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
