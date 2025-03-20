#!/bin/bash
# Script to build and check the package for distribution

echo "=== Preparing pyusacycling package for distribution ==="

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/

# Install build dependencies if not already installed
pip install --upgrade build twine

# Build the package
echo "Building the package..."
python -m build

# Check the built package
echo "Checking the package..."
twine check dist/*

echo "=== Build completed ==="
echo "To upload to PyPI Test:"
echo "twine upload --repository-url https://test.pypi.org/legacy/ dist/*"
echo ""
echo "To upload to PyPI:"
echo "twine upload dist/*" 