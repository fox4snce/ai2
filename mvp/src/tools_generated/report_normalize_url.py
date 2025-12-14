from typing import Dict, Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def _ensure_scheme(url: str) -> str:
    # If url has no scheme, default to https
    parsed = urlparse(url)
    if parsed.scheme:
        return url
    return "https://" + url


def _normalize(url: str) -> str:
    # Add default scheme if missing
    url_with_scheme = _ensure_scheme(url.strip())
    parsed = urlparse(url_with_scheme)

    scheme = parsed.scheme.lower() if parsed.scheme else "https"

    # Hostname lowercased
    hostname = (parsed.hostname or "").lower()

    # Port handling: include if present and not default for scheme
    port = parsed.port
    netloc = hostname
    if port is not None:
        default_port = 443 if scheme == "https" else 80
        if port != default_port:
            netloc = f"{hostname}:{port}"

    # Normalize path:
    # - remove "/" when path is exactly "/"
    # - remove a trailing "/" for non-root paths (so "/a/b/" -> "/a/b")
    path = parsed.path or ""
    if path == "/":
        path = ""
    elif path.endswith("/"):
        path = path[:-1]
    # Do not modify other path segments (deterministic)

    # Sort query parameters for deterministic ordering
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if query_pairs:
        query_pairs.sort()
        query = urlencode(query_pairs, doseq=True)
    else:
        query = ""

    # Remove fragment
    fragment = ""

    normalized = urlunparse((scheme, netloc, path, "", query, fragment))
    return normalized


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
        normalized = _normalize(url)
    except Exception as e:
        return {"final_answer": f"Error: failed to normalize URL: {e}", "error": "normalize_failed"}

    final = {"normalized_url": normalized, "final_answer": f"Normalized URL: {normalized}", "success": True}
    return final
