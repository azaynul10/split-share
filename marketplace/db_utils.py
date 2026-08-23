"""
Raw SQL access layer.

Every database read and write in this project goes through one of the helpers
below. There is no ORM: each helper opens a cursor with a context manager so
it is always closed, and passes user values as parameters rather than string
formatting, so the driver escapes them and SQL injection is not possible.

    # Correct - the driver escapes the value
    fetch_all("SELECT * FROM Users WHERE email = %s", [email])

    # Never do this
    fetch_all(f"SELECT * FROM Users WHERE email = '{email}'")
"""

import logging

from django.db import connection, transaction

logger = logging.getLogger(__name__)


class QueryError(Exception):
    """Raised when a query fails, so views can show a friendly message."""


def dictfetchall(cursor):
    """Return all rows from a cursor as a list of dictionaries."""
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dictfetchone(cursor):
    """Return a single row from a cursor as a dictionary, or None."""
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def fetch_all(sql, params=None):
    """Run a SELECT and return every row as a list of dictionaries."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            return dictfetchall(cursor)
    except Exception as exc:
        logger.error("fetch_all failed: %s\nSQL: %s\nParams: %s", exc, sql, params)
        raise QueryError(str(exc)) from exc


def fetch_one(sql, params=None):
    """Run a SELECT and return the first row as a dictionary, or None."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            return dictfetchone(cursor)
    except Exception as exc:
        logger.error("fetch_one failed: %s\nSQL: %s\nParams: %s", exc, sql, params)
        raise QueryError(str(exc)) from exc


def fetch_scalar(sql, params=None, default=None):
    """Run a SELECT and return the first column of the first row."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            row = cursor.fetchone()
            return row[0] if row else default
    except Exception as exc:
        logger.error("fetch_scalar failed: %s\nSQL: %s\nParams: %s", exc, sql, params)
        raise QueryError(str(exc)) from exc


def execute(sql, params=None):
    """Run an INSERT, UPDATE or DELETE and return the affected row count."""
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                return cursor.rowcount
    except Exception as exc:
        logger.error("execute failed: %s\nSQL: %s\nParams: %s", exc, sql, params)
        raise QueryError(str(exc)) from exc


def insert_returning_id(sql, params=None):
    """Run an INSERT and return the AUTO_INCREMENT id that was generated."""
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                return cursor.lastrowid
    except Exception as exc:
        logger.error(
            "insert_returning_id failed: %s\nSQL: %s\nParams: %s", exc, sql, params
        )
        raise QueryError(str(exc)) from exc


def row_exists(sql, params=None):
    """Return True when a SELECT matches at least one row."""
    return fetch_one(sql, params) is not None
