from typing import List, Optional
import re


def normalize_department_string(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a comma-separated department string:
    - Split on commas
    - Trim spaces
    - Capitalize first letter only (rest lowercase) for each token
    - Join back with ', ' (single space after comma)
    Returns None for empty input.
    """
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p and p.strip()]
    if not parts:
        return None
    def cap_once(s: str) -> str:
        s_clean = s.strip().lower()
        return s_clean[:1].upper() + s_clean[1:] if s_clean else s_clean
    normalized = [cap_once(p) for p in parts]
    return ", ".join(normalized)


def department_tokens_lower(raw: Optional[str]) -> List[str]:
    """Return list of department tokens in lowercase for comparison."""
    if not raw:
        return []
    return [p.strip().lower() for p in raw.split(",") if p and p.strip()]


def department_token_regex_pattern(term: str) -> str:
    """
    Regex pattern to match a token in a comma-separated list, case-insensitive.
    Example: term 'Engineering' -> r'(^|,\\s*)Engineering(\\s*,|$)'
    """
    esc = re.escape(term)
    return fr'(^|,\s*){esc}(\s*,|$)'


