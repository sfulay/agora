
import os

from .base import *


print(DATABASES)
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']


if DATA_TYPE == "cortico":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'agora-iword'),
            'USER': os.environ.get('DB_USER', 'agora_iword'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'local_dev_password'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '6543'),
        }
    }
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'ccc-agora')

else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'ebdb'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'local_dev_password'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '6543'),
        }
    }
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'ccc-sfulay')

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
STATIC_ROOT = f'https://{AWS_S3_CUSTOM_DOMAIN}/static'
#STATIC_ROOT = f'{BASE_DIR}/static_root' 
#STATIC_ROOT = 'static_root'
STATIC_URL = '/static/'
STATICFILES_DIRS = (
    f"{BASE_DIR}/static_dirs",
    f"{BASE_DIR}/static",
)

# Media files configuration
DEFAULT_FILE_STORAGE = 'gabm_infra.utils.MediaRootS3BotoStorage'
MEDIA_ROOT = f'https://{AWS_S3_CUSTOM_DOMAIN}/media'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
