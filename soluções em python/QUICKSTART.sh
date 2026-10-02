#!/bin/bash
# Quick start guide for Hermes Extract

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# List supported formats
echo -e "\n📋 Supported formats:"
"/home/whitefox/Documentos/soluções em python/.venv/bin/python" conversrOFX.py --listar-formatos

# Basic usage - convert to OFX
echo -e "\n✨ Convert PDF to OFX:"
echo "python3 conversrOFX.py extrato.pdf"

# Multiple formats
echo -e "\n✨ Convert to multiple formats:"
echo "python3 conversrOFX.py extrato.pdf --formato ofx,csv,json,xlsx,xml"

# With custom account
echo -e "\n✨ With custom account details:"
echo "python3 conversrOFX.py extrato.pdf --agencia 1234 --conta 5678-9"

# Verbose mode
echo -e "\n✨ Verbose mode (DEBUG logging):"
echo "python3 conversrOFX.py extrato.pdf --verbose"

# Help
echo -e "\n✨ Get help:"
echo "python3 conversrOFX.py --help"

# Run example
echo -e "\n✨ Python programmatic usage:"
echo "See examples.py for 11 different usage patterns"

echo -e "\n📚 Full documentation in README.md"
echo "📝 Implementation details in IMPLEMENTATION_GUIDE.md"
