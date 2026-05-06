from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except User.DoesNotExist:
            self._track_failed_attempt(request, username)
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=username).order_by('id').first()

        if not self.user_can_authenticate(user):
            self._track_failed_attempt(request, username)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        self._track_failed_attempt(request, username)
        return None

    def user_can_authenticate(self, user):
        """Reject inactive users who haven't verified their email."""
        if not user.is_active:
            return False
        return super().user_can_authenticate(user)

    def _track_failed_attempt(self, request, username):
        if request is None:
            return
        try:
            ident = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            # Use a generic logging approach to avoid reverse coupling to prayers.models
            import logging
            logging.getLogger('core.auth').warning(
                'FAILED_LOGIN_ATTEMPT ip=%s user=%s agent=%s',
                ident, username, user_agent
            )
        except Exception:
            pass

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
