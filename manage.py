#!/usr/bin/env python
"""Command-line entry point for the Sub-Share project."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "split_share_core.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django could not be imported. Make sure it is installed and "
            "available on your PYTHONPATH, and that a virtual environment "
            "is activated if you are using one."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
