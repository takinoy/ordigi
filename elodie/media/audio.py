"""
The audio module contains classes specifically for dealing with audio files.
The :class:`Audio` class inherits from the :class:`~elodie.media.Media`
class.

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""

import os
from .media import Media


class Audio(Media):

    """An audio object.

    :param str source: The fully qualified path to the audio file.
    """

    __name__ = 'Audio'

    #: Valid extensions for audio files.
    extensions = ('m4a',)

    def __init__(self, source=None, ignore_tags=set()):
        super().__init__(source, ignore_tags=set())

    def is_valid(self):
        """Check the file extension against valid file extensions.

        The list of valid file extensions come from self.extensions.

        :returns: bool
        """
        source = self.source
        return os.path.splitext(source)[1][1:].lower() in self.extensions
