from __future__ import annotations

from enum import Enum


class CanonicalPrayerStatus(str, Enum):
    ONTIME = "ONTIME"
    LATE = "LATE"
    QADA = "QADA"
    MISSED = "MISSED"


CANONICAL_TO_DB_STATUS = {
    CanonicalPrayerStatus.ONTIME: "on_time",
    CanonicalPrayerStatus.LATE: "late",
    CanonicalPrayerStatus.QADA: "qada",
    CanonicalPrayerStatus.MISSED: "missed",
}

DB_TO_CANONICAL_STATUS = {
    "on_time": CanonicalPrayerStatus.ONTIME,
    "late": CanonicalPrayerStatus.LATE,
    "qada": CanonicalPrayerStatus.QADA,
    "missed": CanonicalPrayerStatus.MISSED,
}

COMPLETION_CANONICAL_STATUSES = {
    CanonicalPrayerStatus.ONTIME,
    CanonicalPrayerStatus.LATE,
    CanonicalPrayerStatus.QADA,
}


def canonical_to_db(status: CanonicalPrayerStatus) -> str:
    return CANONICAL_TO_DB_STATUS[status]


def db_to_canonical(status: str | None) -> CanonicalPrayerStatus | None:
    if status is None:
        return None
    return DB_TO_CANONICAL_STATUS.get(str(status).strip().lower())


def is_completion_status_db(status: str | None) -> bool:
    canonical = db_to_canonical(status)
    return canonical in COMPLETION_CANONICAL_STATUSES

