"""HTTP building blocks for the portal clients.

Important: we do NOT follow redirects automatically - we follow them by hand,
because automatic redirects break the IServ login (OIDC via meta-refresh) and hide
the login-bounce signal. Built on http.client for full control, with no extra
dependencies.
"""

from __future__ import annotations

import http.client
from urllib.parse import quote, urlsplit

from .cookie_jar import CookieJar

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_REQUEST_TIMEOUT = 30


class PortalResponse:
    """A response: status, headers (for Location / Set-Cookie), and body."""

    def __init__(self, status_code, message, body):
        self.status_code = status_code
        self._message = message  # an http.client.HTTPMessage
        self.body = body

    def location(self):
        return self._message.get("location")

    def set_cookie_values(self):
        return self._message.get_all("set-cookie") or []


class PortalHttpClient:
    """A placeholder so the call signatures match the original Java version.

    http.client opens a connection per request, so a shared client object is not
    needed here; it is passed around only for clarity.
    """


def new_client():
    return PortalHttpClient()


def get(client, url, jar, referer):
    return _send(url, "GET", jar, referer=referer)


def post_form(client, url, jar, referer, form):
    return _send(url, "POST", jar, referer=referer,
                 content_type="application/x-www-form-urlencoded", body=_url_encode_form(form))


def post_json(client, url, jar, json_body):
    return _send(url, "POST", jar, content_type="application/json", body=json_body)


def follow_redirects(client, jar, base, start_location, max_hops):
    """Follow up to max_hops redirects and stop at the first non-redirect response."""
    location = start_location
    response = None
    for _ in range(max_hops):
        if location is None:
            break
        absolute = location if location.startswith("http") else base + location
        response = get(client, absolute, jar, base)
        if 300 <= response.status_code < 400:
            location = response.location()
            continue
        break
    return response


def url_encode(value):
    return quote(value, safe="")


# ---------- internal ----------

def _send(url, method, jar, referer=None, content_type=None, body=None):
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    cookie_header = str(jar)
    if cookie_header:
        headers["Cookie"] = cookie_header
    if referer:
        headers["Referer"] = referer
    if content_type:
        headers["Content-Type"] = content_type

    if parts.scheme == "https":
        connection = http.client.HTTPSConnection(parts.hostname, parts.port or 443, timeout=_REQUEST_TIMEOUT)
    else:
        connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=_REQUEST_TIMEOUT)

    try:
        body_bytes = body.encode("utf-8") if body is not None else None
        connection.request(method, path, body=body_bytes, headers=headers)
        response = connection.getresponse()
        text = response.read().decode("utf-8", "replace")
        message = response.msg
        status = response.status
    finally:
        connection.close()

    jar.extract(message.get_all("set-cookie") or [])
    return PortalResponse(status, message, text)


def _url_encode_form(form):
    parts = []
    for key, value in form.items():
        parts.append(url_encode(key) + "=" + url_encode(value if value is not None else ""))
    return "&".join(parts)
