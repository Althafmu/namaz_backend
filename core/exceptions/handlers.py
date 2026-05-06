from rest_framework.response import Response
import logging
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger('core.security')
auth_logger = logging.getLogger('core.auth')


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    request = context.get('request')
    view = context.get('view')

    detail = response.data.get("detail") if isinstance(response.data, dict) else str(response.data)
    field_errors = {}
    if isinstance(response.data, dict):
        for key, value in response.data.items():
            if key != "detail":
                field_errors[key] = value

    status_code = response.status_code

    if request:
        client_ip = _get_client_ip(request)
        path = request.path
        method = request.method
        user = getattr(request, 'user', None)

        if status_code >= 500:
            logger.error(
                'API_ERROR ip=%s path=%s method=%s status=%s error=%s',
                client_ip, path, method, status_code, str(detail)[:200],
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'user': str(user) if user and user.is_authenticated else None,
                    'status': status_code,
                    'detail': str(detail)[:500],
                }
            )
        elif status_code == 401:
            auth_logger.warning(
                'AUTH_FAILURE ip=%s path=%s method=%s status=%s error=%s',
                client_ip, path, method, status_code, str(detail)[:200],
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'status': status_code,
                    'detail': str(detail)[:500],
                }
            )
        elif status_code == 403:
            logger.warning(
                'FORBIDDEN ip=%s path=%s method=%s user=%s status=%s error=%s',
                client_ip, path, method, str(user) if user else None, status_code, str(detail)[:200],
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'user': str(user) if user and user.is_authenticated else None,
                    'status': status_code,
                    'detail': str(detail)[:500],
                }
            )

    return response
