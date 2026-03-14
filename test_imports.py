#!/usr/bin/env python3
"""Test script to verify all imports work correctly."""

try:
    import flask
    print("✓ flask")
    import flask_cors
    print("✓ flask_cors")
    import requests
    print("✓ requests")
    import sentence_transformers
    print("✓ sentence_transformers")
    import faiss
    print("✓ faiss")
    import numpy
    print("✓ numpy")
    import yaml
    print("✓ yaml")
    
    print("\n✅ All imports OK — app.py ready to run!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)
