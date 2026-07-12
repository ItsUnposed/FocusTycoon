"""Text helpers for the portal clients.

On purpose these are regex-based and dependency-free (no HTML parser).
"""

from __future__ import annotations

import re

# Moodle appends a trailing "... ist fällig." (German for "is due") to some
# titles; this matches that so it can be stripped off again.
_TRAILING_DUE = re.compile(r"\s*ist f[äa]llig\.?\s*$", re.IGNORECASE)
# Matches one whole <input ...> tag, so we can look at its attributes.
_INPUT_TAG = re.compile(r"<input\b[^>]*>", re.IGNORECASE | re.DOTALL)
# Matches any HTML tag, used to strip all tags out of a page.
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
# Matches an element whose class name contains "subject", "course" or the
# German "fach", and captures the short text inside it (the subject name).
_SUBJECT_CONTEXT = re.compile(
    r'class="[^"]*(?:subject|course|fach)[^"]*"[^>]*>\s*([^<]{2,30})\s*<',
    re.IGNORECASE | re.DOTALL)


def extract_input_value(html, name):
    """Read the value of an input with the given name (both attribute orders)."""
    escaped_name = re.escape(name)
    # HTML attributes can be written in either order, so first try
    # name="..." followed by value="...".
    match_a = re.search(
        r'<input[^>]*\bname=["\']' + escaped_name + r'["\'][^>]*\bvalue=["\']([^"\']*)["\']',
        html, re.IGNORECASE)
    if match_a:
        return match_a.group(1)
    # Not found that way, so also try value="..." followed by name="...".
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
    # Keep titles from growing unreasonably long (slicing beyond the text
    # length is safe in Python, so this just caps it at 200 characters).
    return title[:min(200, len(title))]


def extract_hidden_inputs(html):
    """Collect all hidden form fields as name -> value (for the IServ login)."""
    fields = {}
    for tag_match in _INPUT_TAG.finditer(html):
        tag = tag_match.group()
        # Only hidden fields matter for re-submitting the login form; skip
        # visible fields like the username/password boxes.
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
    # Replace tags with a space (not nothing), so "word</p><p>word" does not
    # turn into "wordword" once the tags are gone.
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
    """Read one attribute's value out of a single HTML tag string."""
    match = re.search(r'\b' + re.escape(attribute_name) + r'=["\']([^"\']*)["\']', tag, re.IGNORECASE)
    return match.group(1) if match else None
