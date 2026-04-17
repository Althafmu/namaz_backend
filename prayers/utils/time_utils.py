from django.utils import timezone

def get_effective_today():
    """
    Returns the effective date for prayer logging.
    Uses 3 AM cutoff to match streak system.
    """
    now = timezone.localtime()
    if now.hour < 3:
        return (now - timezone.timedelta(days=1)).date()
    return now.date()
