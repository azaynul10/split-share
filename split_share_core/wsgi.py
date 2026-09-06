"""WSGI entry point."""

import os

from django.core.wsgi import get_wsgi_application

from split_share_core.telemetry import setup_telemetry

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "split_share_core.settings")

setup_telemetry()
application = get_wsgi_application()
