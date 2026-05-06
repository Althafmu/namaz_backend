from prayers.models import UserSettings


def ensure_user_settings_exist(user) -> UserSettings:
    """
    Mutation: ensures settings exist for user.
    Communicates side effect via 'ensure' naming.
    """
    settings, _ = UserSettings.objects.get_or_create(user=user)
    return settings
