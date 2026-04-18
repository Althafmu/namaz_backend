from prayers.models import UserSettings


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
