"""ASGI config for the restaurant SaaS project."""

import os

import django
from channels.routing import ProtocolTypeRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from config.routing import application

__all__ = ['application']
