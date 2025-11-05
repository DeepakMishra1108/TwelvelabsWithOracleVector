"""Simple test harness for pegasus_helpers.validate_edit_plan"""
import importlib.util
import os
import sys
import json

module_dir = os.path.abspath('twelvelabvideoai/src')
spec = importlib.util.spec_from_file_location('pegasus_helpers', os.path.join(module_dir, 'pegasus_helpers.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
validate_edit_plan = mod.validate_edit_plan
normalize_plan = mod.normalize_plan

valid_plan = {
    "plan": [
        {"video_file": "oci://media/sample1.mp4", "start": 10.0, "end": 16.0, "caption": "Clip 1"},
        {"video_file": "oci://media/sample2.mp4", "start": 20.0, "end": 25.0, "caption": "Clip 2"}
    ],
    "narrative": "Highlight of key inspection moments."
}

invalid_plan = {
    "plan": [
        {"video_file": "", "start": "ten", "end": 5}
    ],
    # missing narrative
}

for name, plan in [('valid', valid_plan), ('invalid', invalid_plan)]:
    norm = normalize_plan(plan)
    ok, errs = validate_edit_plan(norm, duration_limit=30, max_segments=4)
    print(f'Plan {name}: valid={ok}')
    if errs:
        print(' Errors:')
        for e in errs:
            print('  -', e)
    print()