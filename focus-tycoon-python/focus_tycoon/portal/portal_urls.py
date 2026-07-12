"""URL normalisation for all portal clients.

It reduces any input (even a full OIDC login link) to scheme://host[:port].
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .portal_exception import PortalScrapeException


def origin_of(school_url):
    parts = urlsplit((school_url or "").strip())
    if not parts.scheme or not parts.hostname:
        raise PortalScrapeException("Invalid school URL.")
    origin = f"{parts.scheme}://{parts.hostname}"
    if parts.port:
        origin += f":{parts.port}"
    return origin
