from enum import Enum


class PrayerName(str, Enum):
    FAJR = "fajr"
    DHUHR = "dhuhr"
    ASR = "asr"
    MAGHRIB = "maghrib"
    ISHA = "isha"

    @classmethod
    def choices(cls):
        return [(e.value, e.name) for e in cls]


class PrayerStatus(str, Enum):
    ON_TIME = "on_time"
    LATE = "late"
    QADA = "qada"
    MISSED = "missed"
    PENDING = "pending"
    EXCUSED = "excused"

    @classmethod
    def choices(cls):
        return [(e.value, e.name) for e in cls]


class IntentLevel(str, Enum):
    FOUNDATION = "foundation"
    STRENGTHENING = "strengthening"
    GROWTH = "growth"

    @classmethod
    def choices(cls):
        return [(e.value, e.name) for e in cls]


class RecoveryState(str, Enum):
    PROTECTED = "protected"
    EXPIRED = "expired"
    REQUIRES_QADA = "requires_qada"

    @classmethod
    def choices(cls):
        return [(e.value, e.name) for e in cls]


class GroupRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"

    @classmethod
    def choices(cls):
        return [(e.value, e.name) for e in cls]


class GroupPrivacy(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INVITE_ONLY = "invite_only"
    
    @classmethod
    def choices(cls):
        return [(e.value, e.name) for e in cls]


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    LEFT = "left"
    REMOVED = "removed"
    BANNED = "banned"
    
    @classmethod
    def choices(cls):
        return [(e.value, e.name) for e in cls]


# Group size limits (Issue 10, Fix #13)
GROUP_MAX_MEMBERS = 100
GROUP_MAX_INVITES_ACTIVE = 5
