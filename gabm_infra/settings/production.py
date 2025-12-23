from .base import *
import os
SECRET_KEY = os.environ.get('SECRET_KEY', '***REMOVED***')

DEBUG = False
# ALLOWED_HOSTS = [ '.elasticbeanstalk.com', 'localhost', '127.0.0.1', 
#                  'agoraenv2.eba-euj8emcr.us-east-1.elasticbeanstalk.com',
#                   'awseb--AWSEB-Sj3D95a5c78r-250668400.us-east-1.elb.amazonaws.com' ]
# ALLOWED_HOSTS = [
#     'agora.ccc-mit.org',
#     'agoraenv2.eba-euj8emcr.us-east-1.elasticbeanstalk.com',
#     'awseb--AWSEB-Sj3D95a5c78r-250668400.us-east-1.elb.amazonaws.com',
#     '172.31.41.35',  # Add your EC2 internal IP
#     'localhost',
#     '127.0.0.1',
#     '54.160.196.52'  # Add this line
# ]
ALLOWED_HOSTS = ['*']

# Configure database for RDS
if DATA_TYPE == "cortico":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'agora-iword',
            'USER': 'agora_iword',
            'PASSWORD': '***REMOVED***',
            'HOST': '***REMOVED***',
            'PORT': '5432',
        }
    }
    AWS_STORAGE_BUCKET_NAME = 'ccc-agora'
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'ebdb',
            'USER': 'postgres',
            'PASSWORD': '***REMOVED***',
            'HOST': '***REMOVED***',
            'PORT': '5432',
        }
    }
    AWS_STORAGE_BUCKET_NAME = 'ccc-sfulay'

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_S3_VERIFY = True
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

# Static files configuration
STATICFILES_STORAGE = 'gabm_infra.utils.StaticRootS3BotoStorage'
#STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static'
STATIC_ROOT = f'https://{AWS_S3_CUSTOM_DOMAIN}/static'
#STATIC_ROOT = 'static_root'
STATIC_URL = '/static/'
STATICFILES_DIRS = (
    f"{BASE_DIR}/static_dirs",
)

# Media files configuration
DEFAULT_FILE_STORAGE = 'gabm_infra.utils.MediaRootS3BotoStorage'
MEDIA_ROOT = f'https://{AWS_S3_CUSTOM_DOMAIN}/media'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
#MEDIA_URL = '/media/'
# Add these security settings for HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'handlers': {
#         'console': {
#             'class': 'logging.StreamHandler',
#             'level': 'DEBUG',
#         },
#     },
#     'loggers': {
#         'django': {
#             'handlers': ['console'],
#             'level': 'DEBUG',
#         },
#         'allauth': {  # Add specific allauth logging
#             'handlers': ['console'],
#             'level': 'DEBUG',
#         },
#         'django.request': {
#             'handlers': ['console'],
#             'level': 'DEBUG',
#         },
#     },
# }
