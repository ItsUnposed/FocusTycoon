"""A dependency-free iCalendar (.ics) parser.

It covers the common structure that Google, Outlook, Apple, Moodle and IServ
produce: line unfolding, VEVENT blocks, properties with parameters, text
unescaping, and date / date-time values. Time zones are not converted (this is a
simple version).
"""

from __future__ import annotations

from datetime import datetime

from ..model.calendar_event import CalendarEvent


def parse(ics_content):
    events = []
    if ics_content is None or not ics_content.strip():
        return events

    lines = _unfold(ics_content)

    inside_event = False
    summary = ""
    description = ""
    location = ""
    uid = ""
    start = None
    all_day = False

    for line in lines:
        upper_line = line.upper()
        if upper_line.startswith("BEGIN:VEVENT"):
            # A new event block starts here, so reset all its fields. This
            # also protects us from an earlier event leaking into this one.
            inside_event = True
            summary = ""
            description = ""
            location = ""
            uid = ""
            start = None
            all_day = False
            continue
        if upper_line.startswith("END:VEVENT"):
            # Only keep the event if it has both a start date and a title;
            # otherwise there is nothing useful to show the user.
            if inside_event and start is not None and summary.strip():
                events.append(CalendarEvent(summary, description, location, start, all_day, uid))
            inside_event = False
            continue
        # Properties outside of a VEVENT block (calendar-wide settings, for
        # example) are not something we need, so ignore them.
        if not inside_event:
            continue

        prop = _split_property(line)
        if prop is None:
            continue
        name, value = prop
        if name == "SUMMARY":
            summary = _unescape_text(value)
        elif name == "DESCRIPTION":
            description = _unescape_text(value)
        elif name == "LOCATION":
            location = _unescape_text(value)
        elif name == "UID":
            uid = value.strip()
        elif name == "DTSTART":
            parsed = _parse_date(value.strip())
            if parsed is not None:
                start, all_day = parsed
    return events


def _unfold(content):
    """Join "folded" lines back together.

    The .ics format splits long lines across several physical lines: every
    continuation line starts with a single space or tab, which we need to
    remove before joining it back onto the line above.
    """
    raw_lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result = []
    current = None
    for raw_line in raw_lines:
        if raw_line and (raw_line[0] == " " or raw_line[0] == "\t"):
            # This line is a continuation of the previous one: drop the
            # leading space/tab and glue it onto what came before.
            if current is not None:
                current.append(raw_line[1:])
        else:
            # This line starts something new, so finish the previous line first.
            if current is not None:
                result.append("".join(current))
            current = [raw_line]
    if current is not None:
        result.append("".join(current))
    return result


def _split_property(line):
    """Split a line like "DTSTART;TZID=Europe/Berlin:20250101" into a name and a value.

    Anything between a semicolon and the colon is a parameter (like a time
    zone id) that this simple parser does not need, so it is dropped here.
    """
    colon = line.find(":")
    if colon < 0:
        return None
    name_part = line[:colon]
    value = line[colon + 1:]
    semicolon = name_part.find(";")
    if semicolon >= 0:
        name = name_part[:semicolon]
    else:
        name = name_part
    return name.strip().upper(), value


def _unescape_text(value):
    """Undo the backslash escaping the .ics format uses for text values.

    For example "\\n" means a line break and "\\," means a literal comma.
    We walk through the text one character at a time so we can look ahead by
    one character whenever we see a backslash.
    """
    if "\\" not in value:
        return value
    output = []
    index = 0
    length = len(value)
    while index < length:
        character = value[index]
        if character == "\\" and index + 1 < length:
            # Look at the character right after the backslash to know which
            # escape sequence this is.
            index += 1
            following = value[index]
            if following in ("n", "N"):
                output.append("\n")
            elif following == ",":
                output.append(",")
            elif following == ";":
                output.append(";")
            elif following == "\\":
                output.append("\\")
            else:
                output.append(following)
        else:
            output.append(character)
        index += 1
    return "".join(output)


def _parse_date(value):
    """Parse a DTSTART value, which can be a plain date or a date-time.

    Returns a (datetime, is_all_day) tuple, or None if the value cannot be
    understood.
    """
    try:
        # A trailing "Z" marks UTC. We are not converting time zones in this
        # simple parser (see the module docstring), so we can just drop it.
        text = value[:-1] if value.endswith("Z") else value
        # A date-time value has a "T" separating the date and the time part
        # (for example "20250101T090000"); a plain date does not.
        time_separator_index = text.find("T")
        if time_separator_index < 0:
            if len(text) < 8:
                return None
            date_only = datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]))
            return date_only, True  # all-day, start of the day
        date_part = text[:time_separator_index]
        time_part = text[time_separator_index + 1:]
        if len(date_part) < 8 or len(time_part) < 4:
            return None
        year = int(date_part[0:4])
        month = int(date_part[4:6])
        day = int(date_part[6:8])
        hour = int(time_part[0:2])
        minute = int(time_part[2:4])
        # Seconds are optional in the .ics format, so default to 0 if missing.
        second = int(time_part[4:6]) if len(time_part) >= 6 else 0
        return datetime(year, month, day, hour, minute, second), False
    except (ValueError, IndexError):
        # Anything that does not look like a valid date ends up here; treat
        # it the same as "no date given" instead of crashing the import.
        return None
