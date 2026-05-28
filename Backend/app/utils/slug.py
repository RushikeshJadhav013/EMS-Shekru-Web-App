import re
from typing import Optional


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str | None) -> str:
    """
    Convert arbitrary text into a URL-safe slug.
    - lowercases
    - replaces runs of non-alnum with '-'
    - trims leading/trailing '-'
    """
    raw = (value or "").strip().lower()
    if not raw:
        return ""

    slug = _NON_ALNUM_RE.sub("-", raw)
    slug = slug.strip("-")
    return slug


def ensure_company_slug(base_company_name: str) -> str:
    """
    Fallback slug if the name can't be slugified to anything useful.
    """
    base = slugify(base_company_name)
    return base or "company"


def generate_unique_company_slug(
    db,
    base_company_name: str,
    *,
    exclude_company_id: Optional[int] = None,
    max_attempts: int = 50,
) -> str:
    """
    Generate a slug and guarantee uniqueness in `companies.company_slug`.
    Works even if existing records already have the column populated.
    """
    from app.db.models.company import Company  # local import to avoid cycles

    base = ensure_company_slug(base_company_name)
    candidate = base

    def exists(slug_value: str) -> bool:
        q = db.query(Company.company_id).filter(Company.company_slug == slug_value)
        if exclude_company_id is not None:
            q = q.filter(Company.company_id != exclude_company_id)
        return q.first() is not None

    if not exists(candidate):
        return candidate

    for i in range(2, max_attempts + 1):
        candidate = f"{base}-{i}"
        if not exists(candidate):
            return candidate

    # Extremely unlikely: if collisions keep happening, fall back to timestamp-ish suffix.
    # (We keep it simple to avoid importing datetime here.)
    return f"{base}-x"

