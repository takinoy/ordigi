"""
The video module contains the :class:`Video` class, which represents video
objects (AVI, MOV, etc.).

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""

# load modules
from datetime import datetime

import os
import re
import time

from .media import Media


class Video(Media):

    """A video object.

    :param str source: The fully qualified path to the video file.
    """

    __name__ = 'Video'

    #: Valid extensions for video files.
    extensions = ('avi', 'm4v', 'mov', 'mp4', 'mpg', 'mpeg', '3gp', 'mts')

    def __init__(self, source=None):
        super(Video, self).__init__(source)
        self.date_original = [
            'EXIF:DateTimeOriginal',
            'H264:DateTimeOriginal',
            'QuickTime:ContentCreateDate'
        ]
        self.date_created = [
            'EXIF:CreateDate',
            'QuickTime:CreationDate',
            'QuickTime:CreateDate',
            'QuickTime:CreationDate-und-US',
            'QuickTime:MediaCreateDate'
        ]
        self.date_modified = ['File:FileModifyDate']
        self.title_key = 'XMP:DisplayName'
        self.latitude_keys = [
            'XMP:GPSLatitude',
            # 'QuickTime:GPSLatitude',
            'Composite:GPSLatitude'
        ]
        self.longitude_keys = [
            'XMP:GPSLongitude',
            # 'QuickTime:GPSLongitude',
            'Composite:GPSLongitude'
        ]
        self.latitude_ref_key = 'EXIF:GPSLatitudeRef'
        self.longitude_ref_key = 'EXIF:GPSLongitudeRef'
        self.set_gps_ref = False
