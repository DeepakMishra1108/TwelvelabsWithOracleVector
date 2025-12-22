#!/usr/bin/env python3
"""Download ImageBind model"""
import torch
from imagebind.models import imagebind_model

print("📥 Downloading ImageBind model...")
print("   Size: ~2GB")
print("   This may take 5-10 minutes...")

model = imagebind_model.imagebind_huge(pretrained=True)
print("✅ Model downloaded successfully!")
print(f"   Model type: {type(model).__name__}")
