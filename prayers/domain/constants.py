from enum import Enum


class PrayerName(str, Enum):
    FAJR = "fajr"
    DHUHR = "dhuhr"
    ASR = "asr"
    MAGHRIB = "maghrib"
    ISHA = "isha"


class PrayerStatus(str, Enum):
    ON_TIME = "on_time"
    LATE = "late"
    QADA = "qada"
    MISSED = "missed"
    PENDING = "pending"
    EXCUSED = "excused"


class IntentLevel(str, Enum):
    FOUNDATION = "foundation"
    STRENGTHENING = "strengthening"
    GROWTH = "growth"


class RecoveryState(str, Enum):
    PROTECTED = "protected"
    EXPIRED = "expired"
    REQUIRES_QADA = "requires_qada"
