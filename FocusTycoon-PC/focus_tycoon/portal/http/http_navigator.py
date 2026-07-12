"""A by-hand follower of redirects AND <meta refresh> tags.

The IServ / OIDC login needs this: the OIDC code sometimes comes via meta-refresh
instead of a Location header, and automatic redirects would hide the login-bounce
(auth error) signal.
"""

from __future__ import annotations

import re

from . import portal_http
from .cookie_jar import CookieJar

DEFAULT_MAX_HOPS = 25

_LOGIN_BOUNCE = re.compile(r"/iserv/auth/login(\?|$)")
_META_REFRESH = re.compile(
    r"""<meta[^>]+http-equiv=["']refresh["'][^>]*content=["']\s*\d+\s*;\s*url=([^"']+)["']""",
    re.IGNORECASE)
_REDIRECT_CODES = {301, 302, 303, 307, 308}


class NavResult:
    """The result of a navigation. auth_failed = login bounce / 401 / 403 / hop limit."""

    def __init__(self, status, final_url, html, auth_failed):
        self.status = status
        self.final_url = final_url
        self.html = html
        self.auth_failed = auth_failed


def _failed_result():
    return NavResult(0, None, None, True)


def is_login_bounce(url):
    return url is not None and _LOGIN_BOUNCE.search(url) is not None


def navigate(client, jar: CookieJar, base, start_url, max_hops=DEFAULT_MAX_HOPS):
    url = start_url
    referer = base + "/iserv/"
    for _ in range(max_hops):
        if is_login_bounce(url):
            return _failed_result()  # redirected to the login form -> auth error
        absolute = url if url.startswith("http") else base + url
        response = portal_http.get(client, absolute, jar, referer)
        status = response.status_code
        location = response.location()

        if status in _REDIRECT_CODES and location is not None:
            url = location
            continue
        if status == 200:
            html = response.body
            meta_url = _meta_refresh_url(html)
            if meta_url is not None:
                url = meta_url
                continue
            return NavResult(200, absolute, html, False)
        return NavResult(status, absolute, response.body, status == 401 or status == 403)
    return _failed_result()  # hop limit reached


def _meta_refresh_url(html):
    match = _META_REFRESH.search(html)
    if not match:
        return None
    return match.group(1).replace("&amp;", "&").strip()
