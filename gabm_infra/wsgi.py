"""
WSGI config for gabm_infra project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("1. Starting WSGI initialization")

try:
    logger.debug("2. Current DJANGO_SETTINGS_MODULE: %s", os.environ.get('DJANGO_SETTINGS_MODULE', 'Not Set'))
    
    # Try to import Django
    logger.debug("3. Attempting to import Django...")
    from django.core.wsgi import get_wsgi_application
    
    logger.debug("4. Setting DJANGO_SETTINGS_MODULE...")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gabm_infra.settings.production')
    logger.debug("5. DJANGO_SETTINGS_MODULE now set to: %s", os.environ.get('DJANGO_SETTINGS_MODULE'))
    
    logger.debug("6. Python path: %s", sys.path)
    
    logger.debug("7. Calling get_wsgi_application()...")
    application = get_wsgi_application()
    logger.debug("8. WSGI application created successfully!")

except Exception as e:
    logger.error("❌ Error during WSGI initialization: %s", str(e), exc_info=True)
    raise

logger.debug("9. WSGI initialization complete!")
