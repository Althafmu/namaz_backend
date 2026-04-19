import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
def test_endpoint_paths_unchanged_and_routable():
    client = APIClient()
    user = User.objects.create_user(username='routeuser', password='testpass')
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    checks = [
        ("get", "/api/prayers/today/"),
        ("get", "/api/prayers/history/"),
        ("get", "/api/prayers/history/detailed/"),
        ("get", "/api/prayers/reasons/"),
        ("post", "/api/prayers/log/"),
        ("post", "/api/prayers/excused/"),
        ("post", "/api/prayers/undo/"),
        ("get", "/api/analytics/weekly/"),
        ("get", "/api/sync/metadata/"),
        ("get", "/api/streak/"),
        ("post", "/api/streak/consume-token/"),
        ("post", "/api/notifications/pause-today/"),
        ("get", "/api/notifications/pause-today/"),
        ("patch", "/api/profile/offsets/"),
        ("patch", "/api/user/intent/"),
        ("get", "/api/user/config/"),
    ]

    for method, path in checks:
        fn = getattr(client, method)
        response = fn(path, {})
        assert response.status_code != 404, f"{path} should remain routable"

