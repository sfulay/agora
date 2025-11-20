from storages.backends.s3boto3 import S3Boto3Storage

class StaticRootS3BotoStorage(S3Boto3Storage):
    location = 'static'
    file_overwrite = False

class MediaRootS3BotoStorage(S3Boto3Storage):
    location = 'media'
    file_overwrite = False