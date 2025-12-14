"""
llm_utils.py - OpenAI GPT-5 utilities for text and JSON responses

Usage:
- Ensure you have set OPENAI_API_KEY in your environment
- Import this module and use the provided functions for text and JSON responses
- Supports both regular and high-reasoning modes for complex tasks


"""

import json
import os
import re
import unicodedata
import datetime
from typing import Optional, Dict, Any, TypeVar, Type
import time
from pydantic import BaseModel

# Optional imports: this repo may use llm_utils.py standalone (e.g., MVP toolsmith)
# without the story-writing stack that provides metrics/data_models.
try:
    from metrics import record_llm_duration  # type: ignore
except Exception:
    def record_llm_duration(*_args, **_kwargs):  # type: ignore
        return None

try:
    from data_models import SceneType, AtomType, ArcType  # type: ignore
except Exception:
    SceneType = AtomType = ArcType = None  # type: ignore

T = TypeVar('T', bound=BaseModel)


# Debug metadata for the most recent generate_response_with_auto_continue call.
_last_auto_continue_meta: Dict[str, Any] = {}


def _has_end_marker(text: str, marker: str) -> bool:
    """Check if the marker exists on its own line in the text."""
    if not text or not marker:
        return False
    pattern = re.compile(rf"^\s*{re.escape(marker)}\s*$", re.MULTILINE)
    return bool(pattern.search(text))


def _clean_enum_values(data: Any, model_class: Type[BaseModel]) -> Any:
    """Clean up enum values that might be returned incorrectly by the LLM."""
    # Import here to avoid circular imports
    try:
        from data_models import Atom, Scene  # type: ignore
    except Exception:
        Atom = Scene = None  # type: ignore
    
    if isinstance(data, dict):
        cleaned = {}
        # Check if this looks like an Atom (has type and description, or is in atoms array context)
        is_atom_context = ('description' in data or 'characters_involved' in data) and 'type' in data
        
        for key, value in data.items():
            if isinstance(value, str):
                # Clean up SceneType.INTRO_PROBLEM -> intro_problem
                if value.startswith('SceneType.') and SceneType is not None:
                    enum_name = value.replace('SceneType.', '')
                    try:
                        enum_val = getattr(SceneType, enum_name)
                        cleaned[key] = enum_val.value
                    except AttributeError:
                        # Fallback: try to convert INTRO_PROBLEM -> intro_problem
                        cleaned[key] = enum_name.lower()
                # Clean up AtomType.SPARK -> Spark
                elif value.startswith('AtomType.') and AtomType is not None:
                    enum_name = value.replace('AtomType.', '')
                    try:
                        enum_val = getattr(AtomType, enum_name)
                        cleaned[key] = enum_val.value
                    except AttributeError:
                        cleaned[key] = value
                # Clean up ArcType.POSITIVE -> positive
                elif value.startswith('ArcType.') and ArcType is not None:
                    enum_name = value.replace('ArcType.', '')
                    try:
                        enum_val = getattr(ArcType, enum_name)
                        cleaned[key] = enum_val.value
                    except AttributeError:
                        cleaned[key] = value
                # Fix atom type if it's invalid (especially if it's a scene type)
                elif key == 'type' and is_atom_context:
                    valid_atom_types = ['Spark', 'Tilt', 'Push', 'Block', 'Shift', 'Reveal', 'Break', 'Gain', 'Bind', 'Clash', 'Insight', 'Turn']
                    # Map scene types to appropriate atom types
                    scene_to_atom_map = {
                        'Temptation': 'Tilt', 'temptation': 'Tilt',
                        'Intro': 'Spark', 'intro': 'Spark', 'intro_problem': 'Spark',
                        'Discovery': 'Spark', 'discovery': 'Spark',
                        'Conflict': 'Clash', 'conflict': 'Clash',
                        'Reversal': 'Tilt', 'reversal': 'Tilt',
                        'Bonding': 'Shift', 'bonding': 'Shift',
                        'Decision': 'Push', 'decision': 'Push',
                        'Climax': 'Clash', 'climax': 'Clash',
                        'Aftermath': 'Reveal', 'aftermath': 'Reveal',
                        'Quiet Reflection': 'Insight', 'quiet_reflection': 'Insight', 'quiet reflection': 'Insight'
                    }
                    
                    if value in scene_to_atom_map:
                        cleaned[key] = scene_to_atom_map[value]
                    elif value not in valid_atom_types:
                        # Try to fix case issues
                        value_lower = value.lower()
                        if value_lower in ['spark', 'tilt', 'push', 'block', 'shift', 'reveal', 'break', 'gain', 'bind', 'clash', 'insight', 'turn']:
                            cleaned[key] = value.capitalize()
                        else:
                            # Default to Spark if we can't figure it out
                            cleaned[key] = 'Spark'
                    else:
                        cleaned[key] = value
                else:
                    cleaned[key] = value
            elif isinstance(value, (dict, list)):
                # Recursively clean nested structures
                cleaned[key] = _clean_enum_values(value, model_class)
            else:
                cleaned[key] = value
        return cleaned
    elif isinstance(data, list):
        return [_clean_enum_values(item, model_class) for item in data]
    else:
        return data

_CLIENT = None
_RESP_CLIENT = None


def get_last_auto_continue_meta() -> Dict[str, Any]:
    """Return debug metadata about the last generate_response_with_auto_continue call."""
    return dict(_last_auto_continue_meta)


def _is_test_mode() -> bool:
	return os.getenv("IFE_TEST_MODE", "").strip() == "1"


def _get_client():
	global _CLIENT
	if _CLIENT is not None:
		return _CLIENT
	if _is_test_mode():
		return None
	from openai import OpenAI
	_CLIENT = OpenAI()
	return _CLIENT


def _get_responses_client():
    global _RESP_CLIENT
    if _RESP_CLIENT is not None:
        return _RESP_CLIENT
    if _is_test_mode():
        return None
    from openai import OpenAI
    _RESP_CLIENT = OpenAI()
    return _RESP_CLIENT


def _select_model(fast: bool = False) -> str:
	if _is_test_mode():
		return "test-mode"
	# Global override: if IFE_FORCE_MINI is set, always use the fast model
	if os.getenv("IFE_FORCE_MINI", "").strip() == "1":
		fast_model = os.getenv("IFE_FAST_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
		return fast_model
	main_model = os.getenv("IFE_MAIN_MODEL", "gpt-5.1").strip() or "gpt-5.1"
	fast_model = os.getenv("IFE_FAST_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
	return fast_model if fast else main_model


def is_test_mode() -> bool:
	"""Public helper so other modules can branch for test mode."""
	return _is_test_mode()


def clean_text(text):
    """
    Clean up text by removing or replacing problematic characters.
    
    This function:
    1. Normalizes Unicode characters to their standard form
    2. Replaces common problematic Unicode characters with ASCII equivalents
    3. Removes control characters except for newlines and tabs
    4. Removes byte order marks and zero-width spaces
    5. Handles combining characters by normalizing to composed form first
    """
    if not text:
        return ""
        
    # First normalize to composed form (NFC) to handle combining characters
    text = unicodedata.normalize('NFC', text)
        
    # Define replacements for common problematic characters
    replacements = {
        '\u2018': "'",  # Left single quotation mark
        '\u2019': "'",  # Right single quotation mark
        '\u201c': '"',  # Left double quotation mark
        '\u201d': '"',  # Right double quotation mark
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\u2026': '...', # Ellipsis
        '\u00a0': ' ',  # Non-breaking space
        '\ufeff': '',   # Zero width no-break space (BOM)
        '\u200b': '',   # Zero width space
        '\u200c': '',   # Zero width non-joiner
        '\u200d': '',   # Zero width joiner
        '\u0008': '',   # Backspace
        '\u000b': ' ',  # Vertical tab
        '\u000c': ' ',  # Form feed
        '\u0301': '',   # Combining acute accent
        '\u0300': '',   # Combining grave accent
        '\u0302': '',   # Combining circumflex accent
        '\u0303': '',   # Combining tilde
        '\u0308': '',   # Combining diaeresis
    }
    
    # Apply replacements
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Normalize Unicode characters to decomposed form and then ASCII
    text = unicodedata.normalize('NFKD', text)
    
    # Try to convert to ASCII, ignoring errors
    try:
        text = text.encode('ascii', 'ignore').decode('ascii')
    except UnicodeError:
        # If that fails, keep the unicode but ensure it's clean
        pass
    
    # Remove control characters except for newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    return text


def _extract_output_text(resp) -> str:
    """
    Extract plain text from a Responses API response object in a robust way.

    Prefer the convenience .output_text if present, otherwise fall back to the
    first output.content text chunk.
    """
    # Newer SDKs expose a convenience property
    try:
        output_text = getattr(resp, "output_text", None)
    except Exception:
        output_text = None

    if isinstance(output_text, str) and output_text.strip():
        return output_text

    # Fallback: dig through resp.output[0].content[0].text
    try:
        output = getattr(resp, "output", None)
        if output:
            first = output[0]
            content = getattr(first, "content", None)
            if not content and isinstance(first, dict):
                content = first.get("content")
            if content:
                chunk = content[0]
                if isinstance(chunk, dict):
                    text = chunk.get("text") or chunk.get("output_text") or ""
                else:
                    text = getattr(chunk, "text", "") or getattr(chunk, "output_text", "")
                if isinstance(text, str):
                    return text
    except Exception:
        pass

    # As a last resort, return empty string
    return ""

def generate_response(input_text, system_prompt=None, max_tokens=32768, temperature=0.8, gen_id: Optional[str] = None):
    """
    Generate a text response for prose using the Responses API with reasoning off.

    This is used primarily for scene writing / rewriting where we want:
    - A hard token cap (max_output_tokens)
    - No hidden reasoning tokens (reasoning.effort = "none")
    """
    if _is_test_mode():
        return "TEST_MODE: placeholder text"

    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": input_text})

    try:
        t0 = time.time()
        client = _get_responses_client()
        create_kwargs = {
            "model": _select_model(False),
            "input": msgs,
            "reasoning": {"effort": "none"},
        }
        if max_tokens and max_tokens < 32768:
            create_kwargs["max_output_tokens"] = max_tokens

        resp = client.responses.create(**create_kwargs)

        try:
            record_llm_duration(gen_id or "default.text", time.time() - t0)
        except Exception:
            pass

        return clean_text(_extract_output_text(resp))
    except Exception as e:
        # Fallback: simple chat completions without reasoning controls
        try:
            t0 = time.time()
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": input_text})

            client = _get_client()
            create_kwargs = {
                "model": _select_model(False),
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens and max_tokens < 32768:
                create_kwargs["max_completion_tokens"] = max_tokens

            response = client.chat.completions.create(**create_kwargs)

            try:
                record_llm_duration(gen_id or "default.text", time.time() - t0)
            except Exception:
                pass

            return clean_text(response.choices[0].message.content or "")
        except Exception as e2:
            return f"Error generating response: {str(e2)}"


def generate_response_with_auto_continue(
    input_text: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 32768,
    continuation_max_tokens: Optional[int] = None,
    temperature: float = 0.8,
    gen_id: Optional[str] = None,
    force_marker: Optional[str] = None,
) -> tuple[str, bool, bool]:
    """
    Generate a text response using the Responses API, and if the response is
    marked as incomplete due to max_output_tokens, automatically issue a
    continuation call using previous_response_id and stitch the outputs.

    This is specifically useful for long-form outputs (e.g., scenes) where
    we want to avoid mid-thought cutoffs.
    """
    if _is_test_mode():
        return "TEST_MODE: placeholder text", False, False

    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": input_text})

    # Define logging function outside try block so it's available in except block
    def _log_scene_chunk(label: str, text: str):
        if not text:
            return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_label = re.sub(r"[^A-Za-z0-9_-]", "_", label)
        filename = f"scene_writer_logs/{timestamp}_{safe_label}.txt"
        try:
            os.makedirs("scene_writer_logs", exist_ok=True)
            with open(filename, "w", encoding="utf-8") as log_file:
                log_file.write(text)
        except Exception:
            pass

    client = None
    try:
        t0 = time.time()
        client = _get_responses_client()
        create_kwargs = {
            "model": _select_model(False),
            "input": msgs,
            "reasoning": {"effort": "none"},
        }
        if max_tokens and max_tokens < 32768:
            create_kwargs["max_output_tokens"] = max_tokens

        resp = client.responses.create(**create_kwargs)

        try:
            record_llm_duration(gen_id or "default.text.auto_continue", time.time() - t0)
        except Exception:
            pass

        # Base text from the first response
        base_text = _extract_output_text(resp)
        combined = base_text or ""

        status = getattr(resp, "status", None)
        incomplete = getattr(resp, "incomplete_details", None)
        reason = getattr(incomplete, "reason", None) if incomplete else None

        saw_incomplete_max_tokens = status == "incomplete" and reason == "max_output_tokens"
        forced_continuation_attempted = False

        _log_scene_chunk("initial", base_text or "")

        first_word_count = len((base_text or "").split())
        auto_continue_word_count = 0
        forced_continue_word_count = 0

        # If the model stopped purely because of max_output_tokens, issue a continuation.
        if saw_incomplete_max_tokens:
            # When we need to continue, give the model substantially more headroom.
            cont_tokens = continuation_max_tokens or int(max_tokens * 1.5) or 1024
            cont_kwargs = {
                "model": getattr(resp, "model", _select_model(False)),
                "previous_response_id": getattr(resp, "id", None),
                "input": "Continue from where you stopped. Do NOT repeat previous text. Finish the scene and end with END_OF_SCENE on its own line.",
                "reasoning": {"effort": "low"},
                "text": {"verbosity": "low"},
            }
            if cont_tokens and cont_tokens < 32768:
                cont_kwargs["max_output_tokens"] = cont_tokens

            t1 = time.time()
            resp2 = client.responses.create(**cont_kwargs)
            try:
                record_llm_duration(gen_id or "default.text.auto_continue", time.time() - t1)
            except Exception:
                pass

            tail_text = _extract_output_text(resp2)
            _log_scene_chunk("auto_continue", tail_text or "")
            if tail_text:
                auto_continue_word_count = len(tail_text.split())
                combined = (base_text or "") + "\n" + tail_text

            # Update combined status to whatever the continuation returned.
            status2 = getattr(resp2, "status", None)
            incomplete2 = getattr(resp2, "incomplete_details", None)
            reason2 = getattr(incomplete2, "reason", None) if incomplete2 else None
            if status2 == "incomplete" and reason2 == "max_output_tokens":
                # Still not done—bubble up as a failure so the caller can handle it.
                raise RuntimeError("Continuation call also hit max_output_tokens without finishing.")

            saw_incomplete_max_tokens = False  # continuation finished successfully

        # If a required marker is specified, perform a forced continuation
        # attempt ONLY if the marker is not already present in the combined text.
        if force_marker and not _has_end_marker(combined, force_marker):
            forced_continuation_attempted = True
            cont_tokens = continuation_max_tokens or int(max_tokens * 1.5) or 1024
            cont_kwargs_forced = {
                "model": getattr(resp, "model", _select_model(False)),
                "previous_response_id": getattr(resp, "id", None),
                "input": "You must finish the scene and include END_OF_SCENE on its own line. Continue seamlessly.",
                "reasoning": {"effort": "low"},
                "text": {"verbosity": "low"},
            }
            if cont_tokens and cont_tokens < 32768:
                cont_kwargs_forced["max_output_tokens"] = cont_tokens

            t2 = time.time()
            resp_forced = client.responses.create(**cont_kwargs_forced)
            try:
                record_llm_duration(gen_id or "default.text.auto_continue", time.time() - t2)
            except Exception:
                pass

            forced_tail = _extract_output_text(resp_forced)
            _log_scene_chunk("forced_continue", forced_tail or "")
            if forced_tail:
                forced_continue_word_count = len(forced_tail.split())
                combined = (combined + "\n" + forced_tail).strip()

            status_forced = getattr(resp_forced, "status", None)
            incomplete_forced = getattr(resp_forced, "incomplete_details", None)
            reason_forced = getattr(incomplete_forced, "reason", None) if incomplete_forced else None
            if status_forced == "incomplete" and reason_forced == "max_output_tokens":
                raise RuntimeError("Forced continuation also hit max_output_tokens without finishing.")

        cleaned = clean_text(combined)
        # Record debug metadata for the last auto-continue call.
        global _last_auto_continue_meta
        try:
            _last_auto_continue_meta = {
                "first_word_count": first_word_count,
                "auto_continue_word_count": auto_continue_word_count,
                "forced_continue_word_count": forced_continue_word_count,
                "combined_word_count": len(cleaned.split()),
                "saw_incomplete_max_tokens": saw_incomplete_max_tokens,
                "forced_continuation_attempted": forced_continuation_attempted,
            }
        except Exception:
            pass

        return cleaned, saw_incomplete_max_tokens, forced_continuation_attempted
    except Exception as e:
        # Fallback: use the simpler generate_response logic, but still attempt to enforce
        # the marker requirement by issuing a second call if needed.
        try:
            fallback_text = generate_response(input_text, system_prompt, max_tokens, temperature, gen_id)
            _log_scene_chunk("fallback_initial", fallback_text or "")
            first_word_count = len((fallback_text or "").split())
            forced_continue_word_count = 0
            forced = False
            if force_marker and not _has_end_marker(fallback_text or "", force_marker):
                forced = True
                retry_prompt = (
                    f"{input_text}\n\n"
                    f"The previous attempt did not end with the required marker '{force_marker}'. "
                    f"Rewrite or extend the scene so that it still satisfies all instructions and "
                    f"ends with a line containing only {force_marker}."
                )
                forced_text = generate_response(retry_prompt, system_prompt, max_tokens, temperature, gen_id)
                _log_scene_chunk("fallback_forced", forced_text or "")
                forced_continue_word_count = len((forced_text or "").split())
                fallback_text = forced_text

            cleaned = clean_text(fallback_text or "")
            try:
                _last_auto_continue_meta = {
                    "first_word_count": first_word_count,
                    "auto_continue_word_count": 0,
                    "forced_continue_word_count": forced_continue_word_count,
                    "combined_word_count": len(cleaned.split()),
                    "saw_incomplete_max_tokens": False,
                    "forced_continuation_attempted": forced,
                }
            except Exception:
                pass

            return cleaned, False, forced
        except Exception as e2:
            return f"Error generating response: {str(e2)}", False, False


def generate_response_fast(input_text, system_prompt=None, max_tokens=32768, temperature=0.8, gen_id: Optional[str] = None):
    """
    Fast text response using the Responses API with the "fast" model and reasoning off.
    """
    if _is_test_mode():
        return "TEST_MODE: placeholder text"

    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": input_text})

    try:
        t0 = time.time()
        client = _get_responses_client()
        create_kwargs = {
            "model": _select_model(True),
            "input": msgs,
            "reasoning": {"effort": "none"},
        }
        if max_tokens and max_tokens < 32768:
            create_kwargs["max_output_tokens"] = max_tokens

        resp = client.responses.create(**create_kwargs)

        try:
            record_llm_duration(gen_id or "fast.text", time.time() - t0)
        except Exception:
            pass

        return clean_text(_extract_output_text(resp))
    except Exception as e:
        # Fallback: chat completions with the fast model
        try:
            t0 = time.time()
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": input_text})

            client = _get_client()
            create_kwargs = {
                "model": _select_model(True),
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens and max_tokens < 32768:
                create_kwargs["max_completion_tokens"] = max_tokens

            response = client.chat.completions.create(**create_kwargs)

            try:
                record_llm_duration(gen_id or "fast.text", time.time() - t0)
            except Exception:
                pass

            return clean_text(response.choices[0].message.content or "")
        except Exception as e2:
            return f"Error generating response: {str(e2)}"

def generate_text_response(input_text, system_prompt=None, max_tokens=32768, temperature=0.8):
    """Generate a regular text response using GPT-5."""
    return generate_response(input_text, system_prompt, max_tokens, temperature)

def _repair_json_string_quotes(s: str) -> str:
    """Best-effort repair: escape inner unescaped double quotes inside string values.
    Keeps already valid JSON intact. Only applied when parsing fails.
    """
    try:
        json.loads(s)
        return s  # already valid
    except Exception:
        pass
    repaired = []
    in_str = False
    escape = False
    for ch in s:
        if in_str:
            if escape:
                repaired.append(ch)
                escape = False
            elif ch == '\\':
                repaired.append(ch)
                escape = True
            elif ch == '"':
                in_str = False
                repaired.append(ch)
            elif ch == '\n':
                repaired.append('\\n')
            else:
                repaired.append(ch)
        else:
            if ch == '"':
                in_str = True
                repaired.append(ch)
            else:
                repaired.append(ch)
    return ''.join(repaired)


def generate_json_response(input_text, system_prompt=None, max_tokens=32768, temperature=0.7, gen_id: Optional[str] = None, json_schema: Optional[Dict[str, Any]] = None):
    """Generate JSON; prefer Responses API when available, else fallback to Chat Completions JSON mode."""
    if _is_test_mode():
        return {}
    t0 = time.time()
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    # Ensure "json" appears in messages for OpenAI's requirement when using json_object mode
    json_input_text = input_text
    if not json_schema and "json" not in input_text.lower() and "json" not in (system_prompt or "").lower():
        json_input_text = f"{input_text}\n\nPlease respond with valid JSON."
    msgs.append({"role": "user", "content": json_input_text})
    # Try Responses API first
    resp_client = None
    try:
        resp_client = _get_responses_client()
        if resp_client and hasattr(resp_client, "responses"):
            fmt: Dict[str, Any]
            if json_schema:
                fmt = {"type": "json_schema", "name": json_schema.get("name", "resp"), "schema": json_schema.get("schema", json_schema), "strict": True}
            else:
                fmt = {"type": "json_object"}
            resp = resp_client.responses.create(model=_select_model(False), input=msgs, text={"format": fmt})
            try:
                record_llm_duration(gen_id or "default.json", time.time() - t0)
            except Exception:
                pass
            try:
                return json.loads(resp.output_text)
            except Exception:
                try:
                    return json.loads(resp.output[0].content[0].text)
                except Exception:
                    return {"error": "Failed to parse structured output"}
    except Exception:
        resp_client = None
    # Fallback: Chat Completions with JSON mode
    client = _get_client()
    try:
        cc = client.chat.completions.create(
            model=_select_model(False),
            messages=msgs,
            response_format={"type": "json_object"}
        )
        try:
            record_llm_duration(gen_id or "default.json", time.time() - t0)
        except Exception:
            pass
        return json.loads(cc.choices[0].message.content)
    except Exception as e:
        return {"error": f"Failed to obtain JSON: {e}"}


def generate_json_response_fast(input_text, system_prompt=None, max_tokens=32768, temperature=0.7, gen_id: Optional[str] = None, json_schema: Optional[Dict[str, Any]] = None):
    if _is_test_mode():
        return {}
    t0 = time.time()
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    # Ensure "json" appears in messages for OpenAI's requirement when using json_object mode
    json_input_text = input_text
    if not json_schema and "json" not in input_text.lower() and "json" not in (system_prompt or "").lower():
        json_input_text = f"{input_text}\n\nPlease respond with valid JSON."
    msgs.append({"role": "user", "content": json_input_text})
    # Try Responses API first
    resp_client = None
    try:
        resp_client = _get_responses_client()
        if resp_client and hasattr(resp_client, "responses"):
            fmt: Dict[str, Any]
            if json_schema:
                fmt = {"type": "json_schema", "name": json_schema.get("name", "resp"), "schema": json_schema.get("schema", json_schema), "strict": True}
            else:
                fmt = {"type": "json_object"}
            resp = resp_client.responses.create(model=_select_model(True), input=msgs, text={"format": fmt})
            try:
                record_llm_duration(gen_id or "fast.json", time.time() - t0)
            except Exception:
                pass
            try:
                return json.loads(resp.output_text)
            except Exception:
                try:
                    return json.loads(resp.output[0].content[0].text)
                except Exception:
                    return {"error": "Failed to parse structured output"}
    except Exception:
        resp_client = None
    # Fallback: Chat Completions JSON mode
    client = _get_client()
    try:
        cc = client.chat.completions.create(
            model=_select_model(True),
            messages=msgs,
            response_format={"type": "json_object"}
        )
        try:
            record_llm_duration(gen_id or "fast.json", time.time() - t0)
        except Exception:
            pass
        return json.loads(cc.choices[0].message.content)
    except Exception as e:
        return {"error": f"Failed to obtain JSON: {e}"}

def generate_response_high_reasoning(input_text, system_prompt=None, max_tokens=32768, temperature=0.8):
    """
    Generate a response using GPT-5 with high reasoning effort for complex tasks.
    
    Args:
        input_text (str): The user's input text
        system_prompt (str, optional): System prompt to prepend
        max_tokens (int): Maximum tokens for response (ignored in current API)
        temperature (float): Creativity level (ignored in current API)
    
    Returns:
        str: The generated response text
    """
    if _is_test_mode():
        return "TEST_MODE: placeholder text"
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": input_text})
        client = _get_client()
        response = client.chat.completions.create(model="gpt-5", messages=messages)
        return clean_text(response.choices[0].message.content)
    except Exception as e:
        return f"Error generating response: {str(e)}"

def generate_text_response_high_reasoning(input_text, system_prompt=None, max_tokens=16384, temperature=0.8):
    """Generate a high-reasoning text response using GPT-5."""
    return generate_response_high_reasoning(input_text, system_prompt, max_tokens, temperature)

def generate_json_response_high_reasoning(input_text, system_prompt=None, max_tokens=16384, temperature=0.7):
    if _is_test_mode():
        return {}
    """Generate a high-reasoning JSON response using GPT-5."""
    if system_prompt is None:
        system_prompt = "You are a helpful assistant. Always respond with valid JSON."
    else:
        system_prompt += " Always respond with valid JSON."
    
    response = generate_response_high_reasoning(input_text, system_prompt, max_tokens, temperature)
    
    # Try to extract JSON from code block if it exists
    if '```' in response:
        try:
            json_str = response.split('```')[1]
            if json_str.startswith('json'):
                json_str = json_str[4:]
            json_response = json.loads(json_str.strip())
            return json_response
        except json.JSONDecodeError:
            pass
    
    # If extraction fails or there's no code block, try parsing the whole response
    try:
        json_response = json.loads(response)
        return json_response
    except json.JSONDecodeError:
        # If JSON parsing fails, return an error message in JSON format
        return {"error": "Failed to parse JSON", "raw_response": response}


def _log_validation_error(gen_id: str, error: Exception, prompt: str, system_prompt: Optional[str], model_name: str):
    """Log validation errors for prompt debugging."""
    import datetime
    log_dir = "llm_error_logs"
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"validation_error_{timestamp}_{gen_id.replace('.', '_')}.txt")
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"Validation Error Log\n")
        f.write(f"===================\n\n")
        f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
        f.write(f"Generation ID: {gen_id}\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Error: {str(error)}\n")
        f.write(f"\n{'='*80}\n\n")
        f.write(f"System Prompt:\n")
        f.write(f"{'-'*80}\n")
        f.write(f"{system_prompt or '(none)'}\n")
        f.write(f"\n{'='*80}\n\n")
        f.write(f"User Prompt:\n")
        f.write(f"{'-'*80}\n")
        f.write(f"{prompt}\n")
    
    print(f"      ERROR LOGGED: Validation error saved to {log_file}")


def generate_structured_response(
    pydantic_model: Type[T],
    input_text: str,
    system_prompt: Optional[str] = None,
    fast: bool = False,
    gen_id: Optional[str] = None,
    max_retries: int = 1,
    reasoning_effort: Optional[str] = None,
) -> T:
    """
    Generate a structured response using Pydantic models with OpenAI structured outputs.
    
    Args:
        pydantic_model: The Pydantic model class to use for structured output
        input_text: The user input text
        system_prompt: Optional system prompt
        fast: If True, use fast model (gpt-5-mini), else use main model (gpt-5.1)
        gen_id: Optional generation ID for metrics tracking
        max_retries: Maximum number of retries on validation error (default 1, max 3)
        reasoning_effort: Optional reasoning effort level ("none", "low", "medium", "high"). 
                         Defaults to "none" if not specified.
    
    Returns:
        Instance of the Pydantic model
    """
    if _is_test_mode():
        # Return a test instance with default values
        try:
            return pydantic_model.model_validate({}, strict=False)
        except Exception:
            # If validation fails, try creating with minimal data
            return pydantic_model()
    
    # Hard cap on retries to prevent excessive API calls
    MAX_ALLOWED_RETRIES = 3
    max_retries = min(max(0, max_retries), MAX_ALLOWED_RETRIES)
    
    model_name = _select_model(fast)
    last_error = None
    
    print(f"      [DEBUG] generate_structured_response: model={model_name}, fast={fast}, max_retries={max_retries}, gen_id={gen_id}")
    
    for attempt in range(max_retries + 1):
        try:
            print(f"      [DEBUG] Attempt {attempt + 1}/{max_retries + 1}...")
            t0 = time.time()
            client = _get_responses_client()
            print(f"      [DEBUG] Got client, checking for responses API...")
            if client and hasattr(client, "responses"):
                msgs = []
                if system_prompt:
                    msgs.append({"role": "system", "content": system_prompt})
                msgs.append({"role": "user", "content": input_text})
                
                # Try responses.parse API first (structured outputs with Pydantic)
                try:
                    if hasattr(client.responses, "parse"):
                        print(f"      [DEBUG] Calling client.responses.parse()...")
                        parse_kwargs = {
                            "model": _select_model(fast),
                            "input": msgs,
                            "text_format": pydantic_model
                        }
                        # Add reasoning effort if specified (may not be supported by parse API)
                        if reasoning_effort:
                            parse_kwargs["reasoning"] = {"effort": reasoning_effort}
                        response = client.responses.parse(**parse_kwargs)
                        print(f"      [DEBUG] responses.parse() completed")
                        
                        try:
                            record_llm_duration(gen_id or f"{'fast' if fast else 'default'}.structured", time.time() - t0)
                        except Exception:
                            pass
                        
                        if hasattr(response, "output_parsed"):
                            # Even structured outputs might need validation in some edge cases
                            try:
                                print(f"      [DEBUG] Got output_parsed, returning result")
                                return response.output_parsed
                            except Exception as validation_error:
                                # If output_parsed fails validation, log and retry
                                last_error = validation_error
                                if attempt < max_retries:
                                    _log_validation_error(gen_id or "unknown", validation_error, input_text, system_prompt, model_name)
                                    print(f"      Retry {attempt + 1}/{max_retries}: Validation error from structured output, retrying...")
                                    continue
                                else:
                                    _log_validation_error(gen_id or "unknown", validation_error, input_text, system_prompt, model_name)
                                    raise
                        elif hasattr(response, "output_text"):
                            # Fallback: parse from output_text
                            try:
                                parsed_json = json.loads(response.output_text)
                                parsed_json = _clean_enum_values(parsed_json, pydantic_model)
                                return pydantic_model.model_validate(parsed_json, strict=False)
                            except Exception as parse_error:
                                # If parsing fails, log and retry
                                last_error = parse_error
                                if attempt < max_retries:
                                    _log_validation_error(gen_id or "unknown", parse_error, input_text, system_prompt, model_name)
                                    print(f"      Retry {attempt + 1}/{max_retries}: Parse error from output_text, retrying...")
                                    continue
                                else:
                                    _log_validation_error(gen_id or "unknown", parse_error, input_text, system_prompt, model_name)
                                    raise
                except Exception as parse_error:
                    # If parse API fails, fall through to JSON mode (but only if not a validation error we should retry)
                    if attempt < max_retries and "validation" in str(parse_error).lower():
                        _log_validation_error(gen_id or "unknown", parse_error, input_text, system_prompt, model_name)
                        print(f"      Retry {attempt + 1}/{max_retries}: Parse API error, retrying...")
                        continue
                    # Otherwise fall through to JSON mode
                    pass
                
                # Fallback to JSON mode with schema
                print(f"      [DEBUG] Falling back to JSON mode...")
                # Convert Pydantic model to JSON schema
                # Ensure "json" appears in the prompt for OpenAI's requirement
                json_input_text = input_text
                if "json" not in input_text.lower() and "json" not in (system_prompt or "").lower():
                    json_input_text = f"{input_text}\n\nPlease respond with valid JSON."
                
                json_schema = pydantic_model.model_json_schema()
                print(f"      [DEBUG] Calling generate_json_response (fast={fast})...")
                json_response = generate_json_response_fast(
                    json_input_text, system_prompt, gen_id=gen_id, json_schema={"name": pydantic_model.__name__.lower(), "schema": json_schema}
                ) if fast else generate_json_response(
                    json_input_text, system_prompt, gen_id=gen_id, json_schema={"name": pydantic_model.__name__.lower(), "schema": json_schema}
                )
                print(f"      [DEBUG] JSON response received")
                
                if "error" in json_response:
                    raise ValueError(json_response.get("error", "Failed to generate structured response"))
                
                try:
                    record_llm_duration(gen_id or f"{'fast' if fast else 'default'}.structured", time.time() - t0)
                except Exception:
                    pass
                
                # Clean up enum values that might be returned incorrectly
                json_response = _clean_enum_values(json_response, pydantic_model)
                try:
                    print(f"      [DEBUG] Validating JSON response and returning...")
                    result = pydantic_model.model_validate(json_response, strict=False)
                    print(f"      [DEBUG] Validation successful, returning result")
                    return result
                except Exception as validation_error:
                    # Validation error - log and retry if we have retries left
                    last_error = validation_error
                    if attempt < max_retries:
                        _log_validation_error(gen_id or "unknown", validation_error, input_text, system_prompt, model_name)
                        print(f"      Retry {attempt + 1}/{max_retries}: Validation error, retrying...")
                        continue
                    else:
                        # Out of retries, log and re-raise
                        _log_validation_error(gen_id or "unknown", validation_error, input_text, system_prompt, model_name)
                        raise
            else:
                # Fallback to JSON mode without schema
                # Ensure "json" appears in the prompt for OpenAI's requirement
                json_input_text = input_text
                if "json" not in input_text.lower() and "json" not in (system_prompt or "").lower():
                    json_input_text = f"{input_text}\n\nPlease respond with valid JSON."
                
                json_response = generate_json_response_fast(json_input_text, system_prompt, gen_id=gen_id) if fast else generate_json_response(json_input_text, system_prompt, gen_id=gen_id)
                if "error" in json_response:
                    error_msg = json_response.get("error", "Failed to generate structured response")
                    if attempt < max_retries:
                        print(f"      Retry {attempt + 1}/{max_retries}: API error: {error_msg}, retrying...")
                        continue
                    else:
                        raise ValueError(error_msg)
                
                # Clean up enum values that might be returned incorrectly
                json_response = _clean_enum_values(json_response, pydantic_model)
                try:
                    return pydantic_model.model_validate(json_response, strict=False)
                except Exception as validation_error:
                    # Validation error - log and retry if we have retries left
                    last_error = validation_error
                    if attempt < max_retries:
                        _log_validation_error(gen_id or "unknown", validation_error, input_text, system_prompt, model_name)
                        print(f"      Retry {attempt + 1}/{max_retries}: Validation error, retrying...")
                        continue
                    else:
                        # Out of retries, log and re-raise
                        _log_validation_error(gen_id or "unknown", validation_error, input_text, system_prompt, model_name)
                        raise
        except ValueError as ve:
            # Re-raise ValueError (these are already handled above)
            raise
        except Exception as e:
            # Other errors - retry if we have retries left
            last_error = e
            if attempt < max_retries:
                print(f"      Retry {attempt + 1}/{max_retries}: Error: {str(e)}, retrying...")
                continue
            else:
                # Out of retries, log and raise
                _log_validation_error(gen_id or "unknown", e, input_text, system_prompt, model_name)
                import traceback
                traceback.print_exc()
                raise ValueError(f"Failed to generate structured response after {max_retries + 1} attempts: {e}")
    
    # Should never reach here, but just in case
    if last_error:
        raise ValueError(f"Failed to generate structured response: {last_error}")
    raise ValueError("Failed to generate structured response: Unknown error")

