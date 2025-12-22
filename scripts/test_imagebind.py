#!/usr/bin/env python3
"""Test ImageBind installation"""
import sys
import os
sys.path.insert(0, '/home/dataguardian/TwelvelabsWithOracleVector/src')

print("🧪 Testing ImageBind...")
from utils.imagebind_helper import get_imagebind_embedder

print("📦 Loading ImageBind model...")
embedder = get_imagebind_embedder()
print("✅ ImageBind loaded successfully!")
print(f"   Device: {embedder._device}")
print(f"   Model: {type(embedder._model).__name__}")
