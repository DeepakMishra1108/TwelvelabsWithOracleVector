"""Run a live Pegasus generation using `pegasus_client.generate_plan_from_candidates`.

This script expects TWELVE_LABS_API_KEY in the environment. It uses a deterministic
mock candidate list to request a plan and prints the parsed plan.

Usage: env TWELVE_LABS_API_KEY=... PYTHONPATH=. twelvelabvideoai/bin/python scripts/run_pegasus_live.py
"""
import os
import json
import importlib.util
import sys
from dotenv import load_dotenv

load_dotenv()

# Import the pegasus_client by file path to avoid package import issues in scripts
module_dir = os.path.abspath('twelvelabvideoai/src')
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

spec = importlib.util.spec_from_file_location('pegasus_client', os.path.join(module_dir, 'pegasus_client.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
client = mod

# pegasus_client will import pegasus_helpers; ensure the module dir is on sys.path so imports resolve

mock_candidates = [
    {"video_file": "oci://media/sample1.mp4", "start_time": 10.0, "end_time": 16.0, "score": 0.95},
    {"video_file": "oci://media/sample2.mp4", "start_time": 5.0, "end_time": 12.0, "score": 0.88},
    {"video_file": "oci://media/sample3.mp4", "start_time": 30.0, "end_time": 36.0, "score": 0.80}
]

if not os.getenv('TWELVE_LABS_API_KEY'):
    print('TWELVE_LABS_API_KEY not set in environment; aborting live run.')
    sys.exit(1)

try:
    plan = client.generate_plan_from_candidates(mock_candidates, duration_limit=30, max_segments=3, retries=1)
    print('Generated plan:')
    print(json.dumps(plan, indent=2)[:4000])
except Exception as e:
    print('Pegasus generation failed:', e)
    sys.exit(2)
