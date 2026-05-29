"""Company-scoped office timing resolution helpers."""

from __future__ import annotations

from datetime import time
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models.office_timing import OfficeTiming
from app.utils.department_utils import department_tokens_lower

TimingCache = Tuple[Optional[OfficeTiming], Dict[str, OfficeTiming]]


def normalize_department(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def build_office_timing_cache(db: Session, company_id: int) -> TimingCache:
    records = (
        db.query(OfficeTiming)
        .filter(
            OfficeTiming.is_active.is_(True),
            OfficeTiming.company_id == int(company_id),
        )
        .order_by(OfficeTiming.updated_at.desc())
        .all()
    )

    global_entry: Optional[OfficeTiming] = None
    department_entries: Dict[str, OfficeTiming] = {}

    for entry in records:
        dept_key = normalize_department(entry.department)
        if dept_key is None:
            if global_entry is None or (
                entry.updated_at
                and (global_entry.updated_at is None or entry.updated_at > global_entry.updated_at)
            ):
                global_entry = entry
        else:
            existing = department_entries.get(dept_key)
            if existing is None or (
                entry.updated_at
                and (existing.updated_at is None or entry.updated_at > existing.updated_at)
            ):
                department_entries[dept_key] = entry

    return global_entry, department_entries


def resolve_office_timing(
    db: Session,
    department: Optional[str],
    company_id: int,
    cache: Optional[TimingCache] = None,
) -> Optional[OfficeTiming]:
    if cache is None:
        cache = build_office_timing_cache(db, company_id)
    global_entry, department_entries = cache
    dept_key = normalize_department(department)
    if dept_key:
        if dept_key in department_entries:
            return department_entries[dept_key]

        tokens = department_tokens_lower(dept_key)
        if tokens:
            for token in tokens:
                for key, entry in department_entries.items():
                    key_tokens = department_tokens_lower(key)
                    if token in key_tokens:
                        return entry

    return global_entry


def build_office_timings_map(db: Session, company_id: int) -> Dict[str, OfficeTiming]:
    """Map department name (or __global__) to the active timing for a company."""
    global_entry, department_entries = build_office_timing_cache(db, company_id)
    office_timings_map: Dict[str, OfficeTiming] = dict(department_entries)
    if global_entry is not None:
        office_timings_map["__global__"] = global_entry
    return office_timings_map


def resolve_office_start_time(
    db: Session,
    department: Optional[str],
    company_id: int,
) -> Optional[time]:
    timing = resolve_office_timing(db, department, company_id)
    return timing.start_time if timing else None


def get_timing_for_user_department(
    db: Session,
    *,
    department: Optional[str],
    company_id: Optional[int],
    caches: Optional[Dict[int, TimingCache]] = None,
) -> Optional[OfficeTiming]:
    if company_id is None:
        return None
    company_id = int(company_id)
    if caches is not None:
        if company_id not in caches:
            caches[company_id] = build_office_timing_cache(db, company_id)
        cache = caches[company_id]
    else:
        cache = None
    return resolve_office_timing(db, department, company_id, cache=cache)
