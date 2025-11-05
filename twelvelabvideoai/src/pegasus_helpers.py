"""Helpers for validating and normalizing Pegasus edit plans.

This module is intentionally standalone so it can be imported in tests or CLI tools
without pulling in the full Flask app or external SDKs.
"""
from typing import Tuple, List, Dict, Any


def normalize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize common variations produced by LLMs into the canonical schema.

    - Converts item keys 'start_time'/'end_time' to 'start'/'end'
    - Ensures numeric types for start/end
    - Leaves other keys untouched
    """
    if not isinstance(plan, dict):
        return plan
    normalized = dict(plan)
    items = normalized.get('plan')
    if isinstance(items, list):
        out_items = []
        for it in items:
            if not isinstance(it, dict):
                out_items.append(it)
                continue
            new_it = dict(it)
            if 'start_time' in it and 'start' not in it:
                new_it['start'] = float(it.get('start_time'))
            if 'end_time' in it and 'end' not in it:
                new_it['end'] = float(it.get('end_time'))
            # coerce numeric strings
            try:
                if 'start' in new_it:
                    new_it['start'] = float(new_it['start'])
                if 'end' in new_it:
                    new_it['end'] = float(new_it['end'])
            except Exception:
                # leave as-is; validator will catch bad types
                pass
            out_items.append(new_it)
        normalized['plan'] = out_items
    return normalized


def validate_edit_plan(plan: Dict[str, Any], duration_limit: float = None, max_segments: int = None) -> Tuple[bool, List[str]]:
    """Validate a Pegasus-generated edit plan against the expected schema.

    Returns (is_valid, list_of_error_strings)
    """
    errors: List[str] = []
    if not isinstance(plan, dict):
        return False, ['plan must be a JSON object']

    if 'plan' not in plan:
        errors.append('missing top-level key: plan')
    else:
        if not isinstance(plan['plan'], list):
            errors.append('plan must be an array')

    if 'narrative' not in plan:
        errors.append('missing top-level key: narrative')
    else:
        if not isinstance(plan['narrative'], str):
            errors.append('narrative must be a string')

    if errors:
        return False, errors

    total_duration = 0.0
    items = plan['plan']
    if max_segments is not None and len(items) > max_segments:
        errors.append(f'plan contains {len(items)} items which exceeds max_segments={max_segments}')

    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            errors.append(f'plan[{idx}] must be an object')
            continue
        vf = it.get('video_file')
        if not vf or not isinstance(vf, str):
            errors.append(f'plan[{idx}].video_file must be a non-empty string')
        # start/end
        if 'start' not in it:
            errors.append(f'plan[{idx}] missing required key: start')
        if 'end' not in it:
            errors.append(f'plan[{idx}] missing required key: end')
        # types
        try:
            s = float(it.get('start'))
            e = float(it.get('end'))
            if e <= s:
                errors.append(f'plan[{idx}] end ({e}) must be greater than start ({s})')
            dur = e - s
            total_duration += dur
        except Exception:
            errors.append(f'plan[{idx}] start/end must be numeric (seconds)')

    if duration_limit is not None and total_duration > float(duration_limit) + 1e-6:
        errors.append(f'total duration {total_duration:.2f}s exceeds duration_limit {duration_limit}s')

    is_valid = len(errors) == 0
    return is_valid, errors
