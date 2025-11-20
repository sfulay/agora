#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import socket


def main():
    """Run administrative tasks."""
    hostname = socket.gethostname()
    print(f"Hostname: {hostname}")
    # If running on local machine, use local settings
    if 'prerna' in hostname.lower() or ".dyn.MIT.EDU" in hostname or "suyash" in hostname.lower():  # Add any other local machine names here
        settings_module = 'gabm_infra.settings.local'
    else:
        settings_module = 'gabm_infra.settings.production'
    print(f"Using settings module: {settings_module}")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
