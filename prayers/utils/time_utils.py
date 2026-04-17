from django.utils import timezone

def get_effective_today():
    """
    Returns the effective date for prayer logging.
    Uses midnight rollover to match frontend behavior.
    """
    return timezone.localtime().date()
