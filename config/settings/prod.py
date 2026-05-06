from .base import *
import os
import warnings
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

# Enforce REQUIRED_ENV_VARS in production
REQUIRED_ENV_VARS = ['SECRET_KEY', 'GOOGLE_CLIENT_ID', 'DATABASE_URL']
missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
if missing:
    raise ImproperlyConfigured(f"Missing required environment variables in production: {', '.join(missing)}")

# Security
SECURE_SSL_REDIRECT = True
# ... rest of content ...
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
