"""
The photo module contains the :class:`Photo` class, which is used to track
image objects (JPG, DNG, etc.).

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""

import imghdr
import os
import time

from .media import Media


class Photo(Media):

    """A photo object.

    :param str source: The fully qualified path to the photo file
    """

    __name__ = 'Photo'

    #: Valid extensions for photo files.
    extensions = ('arw', 'cr2', 'dng', 'gif', 'heic', 'jpeg', 'jpg', 'nef', 'png', 'rw2')

    def __init__(self, source=None, ignore_tags=set()):
        super().__init__(source, ignore_tags)

        # We only want to parse EXIF once so we store it here
        self.exif = None

        # Optionally import Pillow - see gh-325
        # https://github.com/jmathai/elodie/issues/325
        self.pillow = None
        try:
            from PIL import Image
            self.pillow = Image
        except ImportError:
            pass


    def is_valid(self):
        """Check the file extension against valid file extensions.

        The list of valid file extensions come from self.extensions. This
        also checks whether the file is an image.

        :returns: bool
        """
        source = self.source

        # HEIC is not well supported yet so we special case it.
        # https://github.com/python-pillow/Pillow/issues/2806
        extension = os.path.splitext(source)[1][1:].lower()
        if(extension != 'heic'):
            # gh-4 This checks if the source file is an image.
            # It doesn't validate against the list of supported types.
            # We check with imghdr and pillow.
            if(imghdr.what(source) is None):
                # Pillow is used as a fallback and if it's not available we trust
                #   what imghdr returned.
                if(self.pillow is None):
                    return False
                else:
                    # imghdr won't detect all variants of images (https://bugs.python.org/issue28591)
                    # see https://github.com/jmathai/elodie/issues/281
                    # before giving up, we use `pillow` imaging library to detect file type
                    #
                    # It is important to note that the library doesn't decode or load the
                    # raster data unless it really has to. When you open a file,
                    # the file header is read to determine the file format and extract
                    # things like mode, size, and other properties required to decode the file,
                    # but the rest of the file is not processed until later.
                    try:
                        im = self.pillow.open(source)
                    except IOError:
                        return False

                    if(im.format is None):
                        return False

        return extension in self.extensions
