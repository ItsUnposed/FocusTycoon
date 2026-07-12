"""Text helpers for the portal clients.

On purpose these are regex-based and dependency-free (no HTML parser).
"""

from __future__ import annotations

import re

_TRAILING_DUE = re.compile(r"\s*ist f[äa]llig\.?\s*$", re.IGNORECASE)
_INPUT_TAG = re.compile(r"<input\b[^>]*>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_SUBJECT_CONTEXT = re.compile(
    r'class="[^"]*(?:subject|course|fach)[^"]*"[^>]*>\s*([^<]{2,30})\s*<',
    re.IGNORECASE | re.DOTALL)


def extract_input_value(html, name):
    """Read the value of an input with the given name (both attribute orders)."""
    escaped_name = re.escape(name)
    match_a = re.search(
        r'<input[^>]*\bname=["\']' + escaped_name + r'["\'][^>]*\bvalue=["\']([^"\']*)["\']',
        html, re.IGNORECASE)
    if match_a:
        return match_a.group(1)
    match_b = re.search(
        r'<input[^>]*\bvalue=["\']([^"\']*)["\'][^>]*\bname=["\']' + escaped_name + r'["\']',
        html, re.IGNORECASE)
    if match_b:
        return match_b.group(1)
    return None


def clean_title(activity_name, name):
    """Title of a Moodle event; removes a trailing '... ist faellig.' and cuts to 200 chars."""
    if activity_name is not None and activity_name.strip():
        title = activity_name
    else:
        title = name if name is not None else ""
    title = _TRAILING_DUE.sub("", title.strip()).strip()
    return title[:min(200, len(title))]


def extract_hidden_inputs(html):
    """Collect all hidden form fields as name -> value (for the IServ login)."""
    fields = {}
    for tag_match in _INPUT_TAG.finditer(html):
        tag = tag_match.group()
        input_type = _attribute(tag, "type")
        if input_type is None or input_type.lower() != "hidden":
            continue
        name = _attribute(tag, "name")
        if not name:
            continue
        value = _attribute(tag, "value")
        fields[name] = value if value is not None else ""
    return fields


def strip_tags(html):
    """Remove tags, decode the common HTML entities, collapse whitespace."""
    if html is None:
        return ""
    text = _TAG.sub(" ", html)
    text = (text
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&#38;", "&")
            .replace("&nbsp;", " ")
            .replace("&amp;", "&"))  # &amp; last (avoids double decoding)
    return _WHITESPACE.sub(" ", text).strip()


def extract_subject_from_context(context):
    """Subject from an HTML context (an element with class subject/course/fach)."""
    if context is None:
        return ""
    match = _SUBJECT_CONTEXT.search(context)
    return match.group(1).strip() if match else ""


def _attribute(tag, attribute_name):
    match = re.search(r'\b' + re.escape(attribute_name) + r'=["\']([^"\']*)["\']', tag, re.IGNORECASE)
    return match.group(1) if match else None
