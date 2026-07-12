"""Portal errors.

Every portal error carries a readable message. Portal errors are never fatal: the
UI catches PortalException and shows the message, but the app never crashes.
"""

from __future__ import annotations


class PortalException(Exception):
    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


class PortalAuthException(PortalException):
    """The login was rejected (wrong credentials or the session was not accepted)."""


class PortalScrapeException(PortalException):
    """Something went wrong while scraping / parsing the portal data."""


class RateLimitedException(PortalException):
    """Synced too often - we still need to wait."""

    def __init__(self, minutes_left):
        super().__init__(f"Please wait {minutes_left} minutes until the next sync.")
        self.minutes_left = minutes_left


class NoCredentialsException(PortalException):
    """There are no saved credentials for this portal."""

    def __init__(self):
        super().__init__("No portal credentials found. Please connect a portal first.")


class DecryptException(PortalException):
    """Decryption failed (wrong key)."""

    def __init__(self):
        super().__init__("The credentials could not be decrypted. Please connect the portal again.")
