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
            inside_event = True
            summary = ""
            description = ""
            location = ""
            uid = ""
            start = None
            all_day = False
            continue
        if upper_line.startswith("END:VEVENT"):
            if inside_event and start is not None and summary.strip():
                events.append(CalendarEvent(summary, description, location, start, all_day, uid))
            inside_event = False
            continue
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
    raw_lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result = []
    current = None
    for raw_line in raw_lines:
        if raw_line and (raw_line[0] == " " or raw_line[0] == "\t"):
            if current is not None:
                current.append(raw_line[1:])
        else:
            if current is not None:
                result.append("".join(current))
            current = [raw_line]
    if current is not None:
        result.append("".join(current))
    return result


def _split_property(line):
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
    if "\\" not in value:
        return value
    output = []
    index = 0
    length = len(value)
    while index < length:
        character = value[index]
        if character == "\\" and index + 1 < length:
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
    try:
        text = value[:-1] if value.endswith("Z") else value
        t_index = text.find("T")
        if t_index < 0:
            if len(text) < 8:
                return None
            date_only = datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]))
            return date_only, True  # all-day, start of the day
        date_part = text[:t_index]
        time_part = text[t_index + 1:]
        if len(date_part) < 8 or len(time_part) < 4:
            return None
        year = int(date_part[0:4])
        month = int(date_part[4:6])
        day = int(date_part[6:8])
        hour = int(time_part[0:2])
        minute = int(time_part[2:4])
        second = int(time_part[4:6]) if len(time_part) >= 6 else 0
        return datetime(year, month, day, hour, minute, second), False
    except (ValueError, IndexError):
        return None
