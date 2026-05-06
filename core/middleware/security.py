import logging
import re
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('core.security')
auth_logger = logging.getLogger('core.auth')
throttle_logger = logging.getLogger('core.throttle')

CLEAR_TEXT_ENDPOINTS = frozenset({
    '/api/auth/login/',
    '/api/auth/register/',
    '/api/auth/password-reset/',
    '/api/auth/password-reset/confirm/',
    '/api/auth/verify-email/',
    '/api/auth/resend-verification/',
})

ANOMALY_PATTERNS = [
    re.compile(rb'<script|>|<|>'),  # XSS probes
    re.compile(rb'union.*select|union select', re.IGNORECASE),  # SQL injection
    re.compile(rb'\.\./', re.IGNORECASE),  # Path traversal
    re.compile(rb'eval\(|base64_decode\(', re.IGNORECASE),  # Code injection
    re.compile(rb'\x00|\x01|\x02'),  # Binary/null bytes in strings
]


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# ... imports and constants ...
def _get_client_ip(request):
# ... implementation ...
# Remove _mask_sensitive() as it is unused
class SecurityEventLoggerMiddleware(MiddlewareMixin):
# ... implementation ...


class SecurityEventLoggerMiddleware(MiddlewareMixin):
    """
    Logs security-relevant events:
    - Failed authentication attempts (tracked via LoginAttempt model)
    - Rate throttle violations (429s)
    - Suspicious request patterns (XSS, SQLi, path traversal probes)
    - High-latency requests (potential DDoS indicators)
    - HTTP method violations on sensitive endpoints
    """

    def process_request(self, request):
        request._security_start_time = time.time()
        request._suspicious_patterns = []

        try:
            body = request.body
            if body:
                for pattern in ANOMALY_PATTERNS:
                    match = pattern.search(body)
                    if match:
                        matched = match.group().decode('utf-8', errors='replace')[:50]
                        request._suspicious_patterns.append(f'body_pattern:{matched}')
        except Exception:
            pass

        query = request.META.get('QUERY_STRING', '')
        if query:
            try:
                for pattern in ANOMALY_PATTERNS:
                    qb = query.encode('utf-8')
                    match = pattern.search(qb)
                    if match:
                        matched = match.group().decode('utf-8', errors='replace')[:50]
                        request._suspicious_patterns.append(f'query_pattern:{matched}')
            except Exception:
                pass

    def process_response(self, request, response):
        client_ip = _get_client_ip(request)
        path = request.path
        method = request.method
        status = response.status_code
        duration = getattr(request, '_security_start_time', None)
        if duration:
            duration = time.time() - duration

        if status == 429:
            throttle_logger.warning(
                'RATE_LIMIT_EXCEEDED ip=%s path=%s method=%s',
                client_ip, path, method,
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'status': status,
                }
            )

        if duration and duration > 5.0:
            logger.warning(
                'SLOW_REQUEST ip=%s path=%s method=%s duration=%.2f status=%s',
                client_ip, path, method, duration, status,
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'duration': round(duration, 3),
                    'status': status,
                }
            )

        user = getattr(request, 'user', None)
        is_authenticated = user and user.is_authenticated

        if status in (401, 403) and path in CLEAR_TEXT_ENDPOINTS and not is_authenticated:
            auth_logger.warning(
                'AUTH_FAILURE ip=%s path=%s method=%s status=%s',
                client_ip, path, method, status,
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'status': status,
                    'detail': 'Authentication failed or forbidden',
                }
            )

        if status == 403:
            logger.warning(
                'FORBIDDEN ip=%s path=%s method=%s user=%s',
                client_ip, path, method, user,
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'user': str(user) if user else None,
                    'status': status,
                }
            )

        suspicious = getattr(request, '_suspicious_patterns', [])
        if suspicious:
            logger.warning(
                'SUSPICIOUS_REQUEST ip=%s path=%s patterns=%s',
                client_ip, path, suspicious,
                extra={
                    'client_ip': client_ip,
                    'path': path,
                    'method': method,
                    'patterns': suspicious,
                    'status': status,
                }
            )

        return response

    def process_exception(self, request, exception):
        client_ip = _get_client_ip(request)
        path = request.path
        logger.error(
            'EXCEPTION ip=%s path=%s exception=%s',
            client_ip, path, str(exception)[:200],
            extra={
                'client_ip': client_ip,
                'path': path,
                'method': request.method,
                'exception': str(exception)[:500],
            },
            exc_info=True,
        )
        return None
