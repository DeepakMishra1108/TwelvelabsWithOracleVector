"""Client wrapper for calling TwelveLabs Pegasus and validating the returned edit plan.

This module focuses on calling the Pegasus model with a provided candidate list
(and not querying the DB). It validates and normalizes the returned JSON plan
using `pegasus_helpers` and will attempt N retries with focused re-prompts if
validation fails.
"""
import os
import json
import time
import logging
from twelvelabs import TwelveLabs
from dotenv import load_dotenv

# Load .env if present so TWELVE_LABS_API_KEY is available
try:
    load_dotenv()
except Exception:
    pass

from pegasus_helpers import normalize_plan, validate_edit_plan

logger = logging.getLogger('pegasus_client')

DEFAULT_MAX_TOKENS = 1500


def _build_prompt(candidates_list, duration_limit, max_segments, style_hint=None):
    """Construct the strict prompt used to ask Pegasus for a JSON-only edit plan."""
    import json as _json
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
    return '\n'.join(prompt_parts)


def _extract_text_from_generation(gen):
    # Try common attributes; fallback to str(gen)
    text = None
    try:
        text = getattr(gen, 'text', None)
    except Exception:
        text = None
    if not text:
        try:
            text = getattr(gen, 'output', None)
        except Exception:
            text = None
    if not text:
        text = str(gen)
    return text


def _invoke_generation(tw, model_name, prompt, max_tokens):
    """Invoke the TwelveLabs generation API in a resilient way.

    Some SDK versions expose `tw.generate.create(...)`, others expose `tw.generate(...)`
    as a callable. This helper tries common invocation patterns and returns the raw
    generation object.
    """
    import inspect

    gen_api = getattr(tw, 'generate', None)

    # Candidate parameter name variations
    model_names = ['model_name', 'model', 'modelName', 'modelId', 'model_id']
    prompt_names = ['prompt', 'input', 'text']
    max_names = ['max_tokens', 'maxTokens', 'max_tokens', 'max_tokens']

    def _attempt_call(fn):
        # Try calling fn with various kwarg combinations
        # Build candidate kwargs sets and try them until one works
        for m in model_names:
            for p in prompt_names:
                for mx in max_names:
                    kwargs = {m: model_name, p: prompt, mx: max_tokens}
                    try:
                        return fn(**kwargs)
                    except TypeError:
                        # signature mismatch; try next
                        pass
                    except Exception:
                        # Other exceptions likely from API; re-raise to let caller handle
                        raise

        # Try with only model and prompt
        for m in model_names:
            for p in prompt_names:
                kwargs = {m: model_name, p: prompt}
                try:
                    return fn(**kwargs)
                except TypeError:
                    pass
                except Exception:
                    raise

        # Try with prompt first (common pattern)
        for p in prompt_names:
            kwargs = {p: prompt}
            try:
                return fn(**kwargs)
            except TypeError:
                pass
            except Exception:
                raise

        # Try positional calls for common patterns
        try:
            # (model_name, prompt, max_tokens)
            return fn(model_name, prompt, max_tokens)
        except TypeError:
            pass
        try:
            # (prompt, model_name)
            return fn(prompt, model_name)
        except TypeError:
            pass
        try:
            # (prompt,)
            return fn(prompt)
        except TypeError:
            pass

        # If nothing worked, raise TypeError to allow caller to try other strategies
        raise TypeError('Could not call generation function with tried signatures')

    # Try object with create method first
    if gen_api is not None:
        create_fn = getattr(gen_api, 'create', None)
        if callable(create_fn):
            try:
                return _attempt_call(create_fn)
            except TypeError:
                # fall through to try gen_api directly
                pass

        if callable(gen_api):
            try:
                return _attempt_call(gen_api)
            except TypeError:
                pass

    # Try other known generation helpers on the client
    for alt in ('generate_text', 'generate_text_sync', 'generate'):  # generate may be a top-level call
        alt_fn = getattr(tw, alt, None)
        if callable(alt_fn):
            try:
                return _attempt_call(alt_fn)
            except TypeError:
                continue

    # Last-resort: attempt to find module-level generation functions
    try:
        tw_mod = __import__('twelvelabs')
        for name in ('generate', 'generate_text', 'generate_text_sync'):
            fn = getattr(tw_mod, name, None)
            if callable(fn):
                try:
                    return _attempt_call(fn)
                except TypeError:
                    continue
    except Exception:
        pass

    raise RuntimeError('Unable to invoke TwelveLabs generation API; unsupported SDK shape or signature')


def generate_plan_from_candidates(candidates_list, duration_limit=60, max_segments=6, style_hint=None, retries=1, max_tokens=DEFAULT_MAX_TOKENS):
    """Call Pegasus to generate an edit plan from the supplied candidates.

    This function will:
    - Build a strict prompt (JSON only)
    - Call Pegasus via TwelveLabs SDK
    - Try to extract a JSON object from the output, normalize and validate it
    - If validation fails, re-prompt once with the validation errors and the model output

    Returns: parsed plan dict on success
    Raises: RuntimeError with diagnostic text on failure
    """
    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        raise RuntimeError('TWELVE_LABS_API_KEY not configured in environment')

    tw = TwelveLabs(api_key=api_key)
    prompt = _build_prompt(candidates_list, duration_limit, max_segments, style_hint)

    attempt = 0
    last_errs = None
    last_output = None
    while attempt <= retries:
        attempt += 1
        try:
            gen = _invoke_generation(tw, model_name='Pegasus', prompt=prompt, max_tokens=max_tokens)
            text = _extract_text_from_generation(gen)
            last_output = text
            # extract first JSON object
            import re
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                last_errs = ['no JSON object found in model output']
                raise ValueError('no JSON')
            parsed = json.loads(m.group(0))
            parsed = normalize_plan(parsed)
            ok, errs = validate_edit_plan(parsed, duration_limit=duration_limit, max_segments=max_segments)
            if ok:
                # attach original text for traceability
                parsed['_raw_model_output'] = text
                return parsed
            else:
                last_errs = errs
                # prepare a focused re-prompt if we have attempts left
                if attempt <= retries:
                    err_text = '; '.join(errs)
                    prompt = (
                        'Your previous JSON output did not validate for the following reasons: ' + err_text + '\n'
                        'Please RETURN ONLY the corrected JSON object that conforms to the schema and requirements previously provided.\n'
                        'Here is the model output you produced: ' + text
                    )
                    # small backoff
                    time.sleep(0.5)
                    continue
                else:
                    raise RuntimeError('Validation failed: ' + '; '.join(errs))
        except Exception as e:
            # If we exhausted retries, raise a diagnostic error
            logger.exception('Pegasus attempt %d failed', attempt)
            if attempt > retries:
                msg = f'Pegasus generation failed after {attempt} attempts. Last error: {e}. Last validation errors: {last_errs}. Last output: {last_output}'
                raise RuntimeError(msg)
            # otherwise, prepare a re-prompt to ask for JSON only
            prompt = (
                'The previous response could not be parsed as JSON or validated. Please RETURN ONLY a single valid JSON object that matches the schema given earlier.\n'
                'If you understand, return only the JSON.\n'
                'Previous output:\n' + (last_output or str(e))
            )
            time.sleep(0.5)
            continue

    # If we fall through, raise with diagnostics
    raise RuntimeError('Pegasus generation failed; final errors: ' + str(last_errs) + '\nlast_output:' + str(last_output))
