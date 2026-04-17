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

    messaging_styles = {
        'foundation': {
            'style': 'soft',
            'pre_miss_nudge': "Don't forget your {prayer} — take a moment for it",
            'post_miss_encouragement': "It's okay. Recovery is always available.",
            'streak_break_message': "Start again today. Stay consistent.",
        },
        'strengthening': {
            'style': 'balanced',
            'pre_miss_nudge': "Your {prayer} time — stay consistent",
            'post_miss_encouragement': "Every prayer counts. Make it up within 24 hours.",
            'streak_break_message': "You broke your streak. Recovery window available.",
        },
        'growth': {
            'style': 'direct',
            'pre_miss_nudge': "{prayer} time now",
            'post_miss_encouragement': "Prioritize your prayers. Recovery window is limited.",
            'streak_break_message': "Streak broken. Focus on getting back on track.",
        },
    }

    nudge_intensities = {
        'foundation': 'light',
        'strengthening': 'medium',
        'growth': 'strong',
    }

    return {
        'intent': intent,
        'messaging_style': messaging_styles.get(intent, messaging_styles['foundation']),
        'nudge_intensity': nudge_intensities.get(intent, 'medium'),
        'flexible_recovery': {
            'allowed_choices': _get_recovery_choices_for_intent(intent),
        },
    }


def _get_recovery_choices_for_intent(intent):
    """
    Returns the list of prayers available for Qada recovery based on intent level.
    Foundation: all missed prayers available
    Others: only priority prayer (first missed in priority order)
    """
    if intent == 'foundation':
        return ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']

    return ['Fajr']


def get_allowed_recovery_choices(user, missed_prayers):
    """
    Returns the list of prayers the user can choose from for Qada recovery.
    Called by views when building recovery UI.

    Args:
        user: Django User instance
        missed_prayers: list of prayer names that were missed (e.g., ['Fajr', 'Asr'])

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

    priority_order = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
    for prayer in priority_order:
        if prayer in missed_prayers:
            return [prayer]

    return []