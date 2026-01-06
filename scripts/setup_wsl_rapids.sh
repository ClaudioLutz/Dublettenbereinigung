#!/bin/bash
# Setup script for RAPIDS/cuML in WSL2
# Run this inside WSL: bash /mnt/c/Lokal_Code/dubletten/scripts/setup_wsl_rapids.sh

set -e

echo "=============================================="
echo "RAPIDS/cuML Setup for WSL2"
echo "=============================================="

# Check NVIDIA GPU access
echo ""
echo "Checking NVIDIA GPU access..."
if nvidia-smi &> /dev/null; then
    echo "✓ NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo "✗ ERROR: nvidia-smi not working. Make sure:"
    echo "  1. NVIDIA drivers are installed on Windows"
    echo "  2. WSL2 is up to date: wsl --update"
    exit 1
fi

# Check/Install Miniforge
echo ""
echo "Checking for conda/miniforge..."
if command -v conda &> /dev/null; then
    echo "✓ Conda found: $(conda --version)"
else
    echo "Installing Miniforge..."
    wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -O /tmp/miniforge.sh
    bash /tmp/miniforge.sh -b -p $HOME/miniforge3
    rm /tmp/miniforge.sh

    # Initialize conda
    $HOME/miniforge3/bin/conda init bash
    source $HOME/.bashrc
    echo "✓ Miniforge installed"
fi

# Ensure conda is in PATH
export PATH="$HOME/miniforge3/bin:$PATH"
source $HOME/miniforge3/etc/profile.d/conda.sh

# Create RAPIDS environment
ENV_NAME="rapids-dedupe"
echo ""
echo "Setting up RAPIDS environment: $ENV_NAME"

if conda env list | grep -q "^$ENV_NAME "; then
    echo "Environment $ENV_NAME already exists. Updating..."
    conda activate $ENV_NAME
else
    echo "Creating new environment with RAPIDS..."
    conda create -n $ENV_NAME -c rapidsai -c conda-forge -c nvidia \
        rapids=25.02 python=3.11 cuda-version=12.0 -y
    conda activate $ENV_NAME
fi

# Install project dependencies
echo ""
echo "Installing project dependencies..."
PROJECT_DIR="/mnt/c/Lokal_Code/dubletten"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip install -r "$PROJECT_DIR/requirements.txt"
    echo "✓ Project dependencies installed"
else
    echo "✗ requirements.txt not found at $PROJECT_DIR"
fi

# Test cuML import
echo ""
echo "Testing cuML import..."
python -c "from cuml import ForestInference; print('✓ cuML ForestInference available')" || echo "✗ cuML import failed"

# Create activation helper
ACTIVATE_SCRIPT="$PROJECT_DIR/scripts/activate_rapids.sh"
cat > "$ACTIVATE_SCRIPT" << 'EOF'
#!/bin/bash
# Quick activation script for RAPIDS environment
# Usage: source /mnt/c/Lokal_Code/dubletten/scripts/activate_rapids.sh

export PATH="$HOME/miniforge3/bin:$PATH"
source $HOME/miniforge3/etc/profile.d/conda.sh
conda activate rapids-dedupe
cd /mnt/c/Lokal_Code/dubletten
echo "RAPIDS environment activated. Run:"
echo "  python scripts/run_dedupe.py --use-ml-scoring --use-gpu ..."
EOF

echo ""
echo "=============================================="
echo "Setup complete!"
echo "=============================================="
echo ""
echo "To use RAPIDS in future WSL sessions:"
echo "  source /mnt/c/Lokal_Code/dubletten/scripts/activate_rapids.sh"
echo ""
echo "To run deduplication with GPU:"
echo "  python scripts/run_dedupe.py --query-file query.sql --out results_ml.csv \\"
echo "      --use-ml-scoring --embeddings-dir models/embeddings --use-gpu"
echo ""
