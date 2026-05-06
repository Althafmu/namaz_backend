from .base import *
import os
import warnings

DEBUG = False

# Enforce SECRET_KEY in production
if not os.environ.get('SECRET_KEY'):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('SECRET_KEY environment variable is required in production.')

# Security
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Database SSL
DATABASES['default']['OPTIONS'] = {
    'sslmode': 'require',
}

# CORS
CORS_ALLOW_ALL_ORIGINS = False
cors_origins_raw = os.environ.get('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_raw.split(',') if origin.strip()]

if not CORS_ALLOWED_ORIGINS:
    warnings.warn('CORS_ALLOWED_ORIGINS is not set in production.')
