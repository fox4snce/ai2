from typing import Dict, Any

from src.tools.normalize import normalize_url


def run(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a URL provided in inputs['url'] and return a deterministic normalized URL.

    Expected input: { 'url': '<user url>' }
    Returns: {
      'normalized_url': '<normalized>',
      'final_answer': 'Normalized URL: <normalized>'
    }
    """
    if not isinstance(inputs, dict):
        return {"final_answer": "Error: inputs must be a dict", "error": "invalid_inputs"}

    url = inputs.get("url")
    if url is None:
        return {"final_answer": "Error: missing 'url' in inputs", "error": "missing_url"}

    if not isinstance(url, str):
        return {"final_answer": "Error: 'url' must be a string", "error": "invalid_url_type"}

    try:
        normalized = normalize_url(url)
    except Exception as e:
        return {"final_answer": f"Error: failed to normalize URL: {e}", "error": "normalize_failed"}

    final = {"normalized_url": normalized, "final_answer": f"Normalized URL: {normalized}", "success": True}
    return final
