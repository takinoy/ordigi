from math import radians, cos, sqrt
from datetime import datetime
import hashlib
import os
import platform
import re
import subprocess


def checksum(file_path, blocksize=65536):
    """Create a hash value for the given file.

    See http://stackoverflow.com/a/3431835/1318758.

    :param str file_path: Path to the file to create a hash for.
    :param int blocksize: Read blocks of this size from the file when
        creating the hash.
    :returns: str or None
    """
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as file:
        buf = file.read(blocksize)

        while len(buf) > 0:
            hasher.update(buf)
            buf = file.read(blocksize)
        return hasher.hexdigest()
    return None


def distance_between_two_points(lat1, lon1, lat2, lon2):
    """Return distance between two points"""
    # From http://stackoverflow.com/questions/15736995/how-can-i-quickly-estimate-the-distance-between-two-latitude-longitude-points  # noqa

    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = list(map(radians, [lat1, lon1, lat2, lon2]))

    rad = 6371000  # radius of the earth in m
    x = (lon2 - lon1) * cos(0.5 * (lat2 + lat1))
    y = lat2 - lat1
    return rad * sqrt(x * x + y * y)


def empty_dir(dir_path):
    return not next(os.scandir(dir_path), None)


def filename_filter(filename):
    """
    Take a string and return a valid filename constructed from the string.
    """
    blacklist = '/\\:*"<>|'
    if filename is None:
        return filename

    # Remove blacklisted chars.
    for char in blacklist:
        filename = filename.replace(char, '')

    return filename


def get_date_regex(user_regex=None):
    """Return date regex generator"""
    if user_regex:
        regex = {'a': re.compile(user_regex)}
    else:
        regex = {
            # regex to match date format type %Y%m%d, %y%m%d, %d%m%Y,
            # etc...
            'a': re.compile(
                r'[-_./](?P<year>\d{4})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})[-_.]?(?P<hour>\d{2})[-_.]?(?P<minute>\d{2})[-_.]?(?P<second>\d{2})'
            ),
            'b': re.compile(
                r'[-_./](?P<year>\d{4})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})[-_./]'
            ),
            # not very accurate
            'c': re.compile(
                r'[-_./](?P<year>\d{2})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})[-_./]'
            ),
            'd': re.compile(
                r'[-_./](?P<day>\d{2})[-_.](?P<month>\d{2})[-_.](?P<year>\d{4})[-_./]'
            ),
        }

    return regex


DATE_REGEX = get_date_regex()


def get_date_from_string(string):
    """Retrieve date stamp from string"""
    # If missing datetime from EXIF data check if filename is in datetime format.
    # For this use a user provided regex if possible.
    # Otherwise assume a filename such as IMG_20160915_123456.jpg as default.

    matches = []
    for i, regex in DATE_REGEX.items():
        match = re.findall(regex, string)
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
            matches.append((match[0], regex))
            # We want only the first match for the moment
            break

    # check if there is only one result
    if len(set(matches)) == 1:
        try:
            # Convert str to int
            date_object = tuple(map(int, matches[0][0]))
            date = datetime(*date_object)
        except (KeyError, ValueError):
            return None

        return date


def match_date_regex(regex, value):
    if re.match(regex, value) is not None:
        return re.sub(regex, r'\g<1>-\g<2>-\g<3>-', value)

    return value


def split_part(dedup_regex, path_part, items=None):
    """
    Split part from regex
    :returns: parts
    """
    if not items:
        items = []

    regex = dedup_regex.pop()
    parts = re.split(regex, path_part)
    # Loop thought part, search matched regex part and proceed with
    # next regex for others parts
    for n, part in enumerate(parts):
        if re.match(regex, part):
            if part[0] in '-_ .':
                if n > 0:
                    # move the separator to previous item
                    parts[n - 1] = parts[n - 1] + part[0]
                items.append(part[1:])
            else:
                items.append(part)
        elif dedup_regex:
            # Others parts
            items = split_part(dedup_regex, part, items)
        else:
            items.append(part)

    return items


# Conversion functions
# source:https://rodic.fr/blog/camelcase-and-snake_case-strings-conversion-with-python/


def snake2camel(name):
    return re.sub(r'(?:^|_)([a-z])', lambda x: x.group(1).upper(), name)


def camel2snake(name):
    return name[0].lower() + re.sub(
        r'(?!^)[A-Z]', lambda x: '_' + x.group(0).lower(), name[1:]
    )


def open_file(path):
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
