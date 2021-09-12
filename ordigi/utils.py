
from math import radians, cos, sqrt
import re

def distance_between_two_points(lat1, lon1, lat2, lon2):
    # As threshold is quite small use simple math
    # From http://stackoverflow.com/questions/15736995/how-can-i-quickly-estimate-the-distance-between-two-latitude-longitude-points  # noqa
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = list(map(
        radians,
        [lat1, lon1, lat2, lon2]
    ))

    r = 6371000  # radius of the earth in m
    x = (lon2 - lon1) * cos(0.5 * (lat2 + lat1))
    y = lat2 - lat1
    return r * sqrt(x * x + y * y)

def get_date_regex(string, user_regex=None):
    if user_regex is not None:
        matches = re.findall(user_regex, string)
    else:
        regex = {
            # regex to match date format type %Y%m%d, %y%m%d, %d%m%Y,
            # etc...
            'a': re.compile(
                r'.*[_-]?(?P<year>\d{4})[_-]?(?P<month>\d{2})[_-]?(?P<day>\d{2})[_-]?(?P<hour>\d{2})[_-]?(?P<minute>\d{2})[_-]?(?P<second>\d{2})'),
            'b': re.compile (
                r'[-_./](?P<year>\d{4})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})[-_./]'),
            # not very accurate
            'c': re.compile (
                r'[-_./](?P<year>\d{2})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})[-_./]'),
            'd': re.compile (
            r'[-_./](?P<day>\d{2})[-_.](?P<month>\d{2})[-_.](?P<year>\d{4})[-_./]')
            }

        for i, rx in regex.items():
            yield i, rx

def get_date_from_string(string, user_regex=None):
    # If missing datetime from EXIF data check if filename is in datetime format.
    # For this use a user provided regex if possible.
    # Otherwise assume a filename such as IMG_20160915_123456.jpg as default.

    matches = []
    for i, rx in get_date_regex(string, user_regex):
        match = re.findall(rx, string)
        if match != []:
            if i == 'c':
                match = [('20' + match[0][0], match[0][1], match[0][2])]
            elif i == 'd':
                # reorder items
                match = [(match[0][2], match[0][1], match[0][0])]
            # matches = match + matches
            if len(match) != 1:
                # The time string is not uniq
                continue
            matches.append((match[0], rx))
            # We want only the first match for the moment
            break

    # check if there is only one result
    if len(set(matches)) == 1:
        try:
            # Convert str to int
            date_object = tuple(map(int, matches[0][0]))

            time = False
            if len(date_object) > 3:
                time = True

            date = datetime(*date_object)
        except (KeyError, ValueError):
            return None

        return date

