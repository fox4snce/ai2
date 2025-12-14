def run(inputs: dict) -> dict:
    """
    Normalize a phone number to a deterministic E.164-like string.

    Expected input format (per contract):
      { "kind": "normalize_phone", "phone": "..." }

    Normalization rules (deterministic):
    - Strip surrounding whitespace.
    - If the original string starts with '+', preserve as international and return '+' + all digits found.
    - Otherwise, extract all digits. If 10 digits -> assume US and prefix '+1'.
      If 11 digits and starts with '1' -> prefix '+'.
      Otherwise return '+' + digits (best-effort).
    - If no digits found, return empty string for normalized.

    Returns a dict containing at least 'final_answer' (string) and 'normalized' (string).
    """
    if not isinstance(inputs, dict):
        raise TypeError('inputs must be a dict')
    from src.tools.normalize import normalize_phone
    phone = inputs.get('phone', '')
    if phone is None:
        phone = ''
    if not isinstance(phone, str):
        phone = str(phone)
    original = phone
    normalized = normalize_phone(phone)
    final_answer = f"normalized_phone: {normalized}"
    return {
        'final_answer': final_answer,
        'normalized': normalized,
        'original': original
    }
