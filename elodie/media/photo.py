"""
The photo module contains the :class:`Photo` class, which is used to track
image objects (JPG, DNG, etc.).

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""

import imagehash
import imghdr
import logging
import numpy as np
import os
from PIL import Image
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


class CompareImages:
    def __init__(self, file_paths, hash_size=8, logger=logging.getLogger()):
        self.file_paths = file_paths
        self.hash_size = hash_size
        self.logger = logger
        logger.setLevel(logging.INFO)

    def get_images(self):
        '''
        :returns: img_path generator
        '''
        for img_path in self.file_paths:
            if imghdr.what(img_path) is not None:
                yield img_path


    def find_duplicates(self):
        """
        Find duplicates
        """

        hashes = {}
        duplicates = []
        # Searching for duplicates.
        for img_path in self.get_images():
            if imghdr.what(img_path) is not None:
                with Image.open(img_path) as img:
                    temp_hash = imagehash.average_hash(img, self.hash_size)
                    if temp_hash in hashes:
                        self.logger.info("Duplicate {} \nfound for image {}\n".format(img_path, hashes[temp_hash]))
                        duplicates.append(img_path)
                    else:
                        hashes[temp_hash] = img_path

        return duplicates


    def remove_duplicates(self, duplicates):
        for duplicate in duplicates:
            try:
                os.remove(duplicate)
            except OSError as error:
                self.logger.error(error)


    def remove_duplicates_interactive(self, duplicates):
        if len(duplicates) != 0:
            answer = input(f"Do you want to delete these {duplicates} images? Y/n: ")
            if(answer.strip().lower() == 'y'):
                self.remove_duplicates(duplicates)
                self.logger.info(f'{duplicate} deleted successfully!')
        else:
            self.logger.info("No duplicates found")


    def find_similar(self, image, similarity=80):
        '''
        Find similar images
        :returns: img_path generator
        '''
        threshold = 1 - similarity/100
        diff_limit = int(threshold*(self.hash_size**2))

        hash1 = ''
        if imghdr.what(image) is not None:
            with Image.open(image) as img:
                hash1 = imagehash.average_hash(img, self.hash_size).hash

        self.logger.info(f'Finding similar images to {image}')
        for img_path in self.get_images():
            if img_path == image:
                continue
            with Image.open(img_path) as img:
                hash2 = imagehash.average_hash(img, self.hash_size).hash

                diff_images = np.count_nonzero(hash1 != hash2)
                if diff_images <= diff_limit:
                    threshold_img = diff_images / (self.hash_size**2)
                    similarity_img = round((1 - threshold_img) * 100)
                    self.logger.info(f'{img_path} image found {similarity_img}% similar to {image}')
                    yield img_path


