from .base import *
import os

DEBUG = True

# Allow all origins in dev
CORS_ALLOW_ALL_ORIGINS = True

# Local development can use a fixed secret if not provided
if not os.environ.get('SECRET_KEY'):
    import warnings
    warnings.warn('Using insecure default SECRET_KEY for development.')
    SECRET_KEY = 'django-insecure-local-dev-key-not-for-production-use'
