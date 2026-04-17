from .models import UserSettings


def get_user_behavior_config(user):
    """
    Returns behavioral configuration for a user based on their intent level.
    Used to drive messaging style, nudge intensity, and recovery flexibility.
    """
    try:
        settings = user.settings
        intent = settings.intent_level
    except UserSettings.DoesNotExist:
        intent = 'foundation'

    styles = {
        'foundation': 'soft',
        'strengthening': 'balanced',
        'growth': 'direct',
    }
    
    nudge_intensities = {
        'foundation': 'light',
        'strengthening': 'medium',
        'growth': 'strong',
    }

    return {
        'intent': intent,
        'style': styles.get(intent, 'soft'),
        'nudge_intensity': nudge_intensities.get(intent, 'medium'),
        'flexible_recovery': intent == 'foundation',
    }


def get_allowed_recovery_choices(user, missed_prayers):
    """
    Returns the list of prayers the user can choose from for Qada recovery.
    Called by views when building recovery UI.

    Args:
        user: Django User instance
        missed_prayers: list of prayer names that were missed (e.g., ['fajr', 'asr'])

    Returns:
        list of prayer names available for recovery selection
    """
    try:
        settings = user.settings
        intent = settings.intent_level
    except UserSettings.DoesNotExist:
        intent = 'foundation'

    if intent == 'foundation':
        return missed_prayers

    priority_order = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    for prayer in priority_order:
        if prayer in missed_prayers:
            return [prayer]

    return []