"""Run dry-run Pegasus prompt generation with mocked candidates for quick validation.

Usage: PYTHONPATH=twelvelabvideoai/src python scripts/dry_run_pegasus.py
"""
import json
import sys
import importlib.util
import os
from dotenv import load_dotenv

load_dotenv()

# Ensure the module's directory is on sys.path so its relative imports resolve
def generate_edit_plan_with_pegasus_local(queries, duration_limit=60, max_segments=6, style_hint=None, top_k=20, dry_run=False, candidates_override=None):
    """Local reproduction of the prompt generation logic from agent_playback_app.generate_edit_plan_with_pegasus
    This function implements only the dry_run prompt/candidates behavior so it can be run without importing the full app.
    """
    import json as _json
    # Use provided candidates or a fallback
    if candidates_override is not None:
        candidates_list = candidates_override[:top_k]
    else:
        # Fallback: empty candidate list
        candidates_list = []

    schema_example = {
        "plan": [
            {
                "video_file": "oci://namespace/bucket/object.mp4",
                "start": 1.23,
                "end": 6.78,
                "caption": "Short caption for the clip",
                "narrator_text": "One-sentence narration for this clip"
            }
        ],
        "narrative": "A one-paragraph overall narrative describing the assembled highlight"
    }

    prompt_parts = [
        'You are Pegasus. Return ONLY a single valid JSON object and NOTHING else (no surrounding text).',
        'Produce an edit plan for a short highlight video that can be constructed by concatenating short clips from the candidate segments.',
        f'Max total duration (seconds): {duration_limit}. Max segments: {max_segments}.',
    ]
    if style_hint:
        prompt_parts.append(f'Style hint: {style_hint}.')
    prompt_parts.append('Candidates:')
    prompt_parts.append(_json.dumps(candidates_list))
    prompt_parts.append('Return JSON matching this example schema (use the same keys and types):')
    prompt_parts.append(_json.dumps(schema_example, indent=2))
    prompt_parts.append('Requirements:')
    prompt_parts.append('- The top-level object MUST have keys "plan" (array) and "narrative" (string).')
    prompt_parts.append('- Each plan item MUST include video_file (string), start (float seconds), end (float seconds).')
    prompt_parts.append('- Optional keys per item: caption (string), narrator_text (string), transition (string).')
    prompt_parts.append('- Use seconds as floats for start/end. Ensure start < end and durations sum to <= Max total duration.')
    prompt_parts.append('Return ONLY the JSON object. No markdown, no explanation, no extra text.')
    prompt = '\n'.join(prompt_parts)

    if dry_run:
        return {'prompt': prompt, 'candidates': candidates_list}

    # Non-dry run behavior (not implemented in this local helper)
    raise RuntimeError('Non-dry-run Pegasus invocation not supported in dry_run script')

generate_edit_plan_with_pegasus = generate_edit_plan_with_pegasus_local

mock_candidates = [
    {"video_file": "oci://media/sample1.mp4", "start_time": 10.0, "end_time": 16.0, "score": 0.95},
    {"video_file": "oci://media/sample2.mp4", "start_time": 5.0, "end_time": 12.0, "score": 0.88},
    {"video_file": "oci://media/sample3.mp4", "start_time": 30.0, "end_time": 36.0, "score": 0.80}
]

queries = [
    ['inspection tower'],
    ['crane maintenance'],
    ['safety harness failure'],
    ['wind turbine inspection'],
    ['bridge structural crack']
]

for q in queries:
    res = generate_edit_plan_with_pegasus(q, duration_limit=30, max_segments=4, dry_run=True, candidates_override=mock_candidates)
    print('--- QUERY:', ', '.join(q))
    print('PROMPT:\n')
    print(res['prompt'])
    print('\nCANDIDATES:')
    print(json.dumps(res['candidates'], indent=2))
    print('\n')
