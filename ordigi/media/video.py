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

    def __init__(self, source=None, ignore_tags=set()):
        super().__init__(source, ignore_tags=set())
        # self.set_gps_ref = False


    def is_valid(self):
        """Check the file extension against valid file extensions.

        The list of valid file extensions come from self.extensions.

        :returns: bool
        """
        source = self.source
        return os.path.splitext(source)[1][1:].lower() in self.extensions
