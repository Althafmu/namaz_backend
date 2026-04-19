from prayers.models import UserSettings


def get_user_behavior_config(user):
    """
    Returns behavioral configuration for a user based on their intent level.
    Used to drive messaging style, nudge intensity, and recovery flexibility.
    """
    try:
        settings = user.settings
        intent = settings.intent_level
        sunnah_enabled = settings.sunnah_enabled
        intent_explicitly_set = settings.intent_explicitly_set
    except UserSettings.DoesNotExist:
        intent = 'foundation'
        sunnah_enabled = False
        intent_explicitly_set = False

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
        'intent_level': intent,
        'intent_explicitly_set': intent_explicitly_set,
        'style': styles.get(intent, 'soft'),
        'nudge_intensity': nudge_intensities.get(intent, 'medium'),
        'flexible_recovery': intent == 'foundation',
        'sunnah_enabled': sunnah_enabled,
    }
