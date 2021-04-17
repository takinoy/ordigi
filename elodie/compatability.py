import os
import shutil
import sys

from elodie import constants


def _decode(string, encoding=sys.getfilesystemencoding()):
    """Return a utf8 encoded unicode string.

    Python2 and Python3 differ in how they handle strings.
    So we do a few checks to see if the string is ascii or unicode.
    Then we decode it if needed.
    """
    if hasattr(string, 'decode'):
        # If the string is already unicode we return it.
        try:
            if isinstance(string, unicode):
                return string
        except NameError:
            pass

        return string.decode(encoding)

    return string

def _bytes(string):
    if constants.python_version == 3:
        return bytes(string, 'utf8')
    else:
        return bytes(string)

