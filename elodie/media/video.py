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
        super().__init__(source)
        # self.set_gps_ref = False


    def is_valid(self):
        return super().is_valid()
