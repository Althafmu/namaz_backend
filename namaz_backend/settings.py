"""
Django settings for namaz_backend project.
"""

import os
import warnings
from pathlib import Path
from datetime import timedelta
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY: SECRET_KEY must be set via environment variable in production.
# Local development can use the default, but production MUST set SECRET_KEY.
SECRET_KEY = os.environ.get('SECRET_KEY')

if not SECRET_KEY:
    if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'):
        raise ImproperlyConfigured(
            'SECRET_KEY environment variable is required in production. '
            'Set it in your deployment platform settings.'
        )
    # Local development fallback only
    SECRET_KEY = 'django-insecure-local-dev-key-not-for-production-use'
    warnings.warn(
        'Using insecure default SECRET_KEY. Set SECRET_KEY environment variable for security.',
        UserWarning
    )

# True if locally, False if deployed and DEBUG not explicitly set to True
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    '.onrender.com,localhost,127.0.0.1'
).split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    # Local
    'prayers',
    'sunnah',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Serve static files in prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'prayers.middleware.SecurityEventLoggerMiddleware',
]

ROOT_URLCONF = 'namaz_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'namaz_backend.wsgi.application'

# Database — SQLite for development, swap to PostgreSQL for production
# If DATABASE_URL is set (like on Railway), use it. Otherwise fallback to sqlite3.
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR}/db.sqlite3',
        conn_max_age=600,
        # SQLite does not support sslmode; only enforce ssl when DATABASE_URL is used.
        ssl_require=(not DEBUG and bool(os.environ.get('DATABASE_URL')))
    )
}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Use bcrypt-compatible hasher for better password security
# Django's default PBKDF2 is fine, but bcrypt is stronger against GPU attacks
# Note: requires bcrypt package. Falls back to Argon2 if available.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Use whitenoise to compress and cache static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email configuration (configure SMTP in production)
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@falah.app')
FAKE_EMAIL_ENABLED = os.environ.get('FAKE_EMAIL_ENABLED', 'True').lower() == 'true'

# CORS — strict allowlist in production
cors_origins_raw = os.environ.get('CORS_ALLOWED_ORIGINS', '')
cors_origins = [origin.strip() for origin in cors_origins_raw.split(',') if origin.strip()]
is_production_env = bool(os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT'))
if DEBUG or not is_production_env:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    if cors_origins:
        CORS_ALLOWED_ORIGINS = cors_origins
    else:
        warnings.warn(
            'CORS_ALLOWED_ORIGINS is not set in production. Browser-based cross-origin '
            'requests will be blocked until allowed origins are configured.',
            UserWarning,
        )

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'EXCEPTION_HANDLER': 'prayers.utils.exception_handler.api_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
        'register': '5/minute',
        'prayer_log': '30/minute',
        'password_reset': '3/minute',
        'login': '5/minute',
        'ai_generation': '10/minute',
        'history_export': '5/minute',
    },
    'NON_FIELD_ERRORS_KEY': 'detail',
}

if is_production_env:
    try:
        hsts_seconds = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    except ValueError:
        hsts_seconds = 31536000
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = hsts_seconds
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Security: Prevent clickjacking
    X_FRAME_OPTIONS = 'DENY'
    # Security: Reference-scopedReferrer
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    # Security: Force content-type sniffing protection
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Security: Browserdeny browserdeny
    SECURE_BROWSER_XSS_FILTER = True

# ─── LOGGING ─────────────────────────────────────────────────────────────────
# Structured logging for security audit trails and anomaly detection.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
        'security': {
            'format': '{asctime} {levelname} {name} ip={client_ip} user={user} path={path} method={method} status={status} detail={detail}',
            'style': '{',
        },
        'auth': {
            'format': '{asctime} AUTH {levelname} action={action} ip={client_ip} username={username} success={success} detail={detail}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['require_debug_false'],
        },
        'security_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'security',
            'filters': ['require_debug_false'],
        },
        'auth_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'auth.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'auth',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['console', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'prayers.security': {
            'handlers': ['console', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'prayers.auth': {
            'handlers': ['console', 'auth_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'prayers.throttle': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / 'logs').mkdir(exist_ok=True)

# Simple JWT
AUTHENTICATION_BACKENDS = [
    'prayers.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),  # Short-lived for security
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),   # Refresh tokens are rotated
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'TOKEN_OBTAIN_SERIALIZER': 'prayers.serializers.CustomTokenObtainPairSerializer',
}

# Google Sign-In
GOOGLE_CLIENT_ID = os.environ.get(
    'GOOGLE_CLIENT_ID',
    '888527789566-qfojbi63uai8v6d726l4iqcuck02adoo.apps.googleusercontent.com'
)
