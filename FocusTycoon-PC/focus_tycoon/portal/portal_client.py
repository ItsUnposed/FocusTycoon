"""A portal-specific client that logs in and reads homework.

Implementations: LogineoClient (Moodle JSON), IServClient (HTML scraping). On a
login / scrape problem they raise a PortalException with a readable message.

This is a base class; real clients override scrape().
"""

from __future__ import annotations


class PortalClient:
    def scrape(self, school_url, username, password, debug):
        raise NotImplementedError("scrape() must be implemented by a subclass")
