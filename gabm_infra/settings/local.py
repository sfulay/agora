
import os

from .base import *


print(DATABASES)
SECRET_KEY = os.environ.get("SECRET_KEY", "***REMOVED***")
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']


if DATA_TYPE == "cortico":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'agora-iword',
            'USER': 'agora_iword',
            'PASSWORD': '***REMOVED***',
            'HOST': 'localhost',
            'PORT': '6543',
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
            'HOST': 'localhost',
            'PORT': '6543',
        }
    }
    AWS_STORAGE_BUCKET_NAME = 'ccc-sfulay'

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
# print(AWS_ACCESS_KEY_ID)
# print(AWS_SECRET_ACCESS_KEY)
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
