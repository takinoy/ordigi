"""
The audio module contains classes specifically for dealing with audio files.
The :class:`Audio` class inherits from the :class:`~elodie.media.Media`
class.

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""

from .media import Media


class Audio(Media):

    """An audio object.

    :param str source: The fully qualified path to the audio file.
    """

    __name__ = 'Audio'

    #: Valid extensions for audio files.
    extensions = ('m4a',)

    def __init__(self, source=None):
        super().__init__(source)

    def is_valid(self):
        return super().is_valid()
