"""
The image module contains the :class:`Images` class, which is used to track
image objects (JPG, DNG, etc.).

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""

import imagehash
import imghdr
import logging
import numpy as np
import os
from PIL import Image as img
from PIL import UnidentifiedImageError
import time

# HEIC extension support (experimental, not tested)
PYHEIF = False
try:
    from pyheif_pillow_opener import register_heif_opener

    PYHEIF = True
    # Allow to open HEIF/HEIC image from pillow
    register_heif_opener()
except ImportError as e:
    pass


class Image:
    def __init__(self, img_path, hash_size=8):

        self.img_path = img_path
        self.hash_size = hash_size

    def is_image(self):
        """Check whether the file is an image.
        :returns: bool
        """
        # gh-4 This checks if the file is an image.
        # It doesn't validate against the list of supported types.
        # We check with imghdr and pillow.
        if imghdr.what(self.img_path) is None:
            # Pillow is used as a fallback
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
                im = img.open(self.img_path)
            except (IOError, UnidentifiedImageError):
                return False

            if im.format is None:
                return False

        return True

    def get_hash(self):
        try:
            with img.open(self.img_path) as image:
                return imagehash.average_hash(image, self.hash_size).hash
        except (OSError, UnidentifiedImageError):
            return None


class Images:

    """A image object.

    :param str img_path: The fully qualified path to the image file
    """

    #: Valid extensions for image files.
    extensions = (
        'arw',
        'cr2',
        'dng',
        'gif',
        'heic',
        'jpeg',
        'jpg',
        'nef',
        'png',
        'rw2',
    )

    def __init__(self, images=set(), hash_size=8, logger=logging.getLogger()):

        self.images = images
        self.duplicates = []
        self.hash_size = hash_size
        self.logger = logger.getChild(self.__class__.__name__)
        if PYHEIF == False:
            self.logger.info("No module named 'pyheif_pillow_opener'")

    def add_images(self, file_paths):
        for img_path in file_paths:
            image = Image(img_path)
            if image.is_image():
                self.images.add(image)

    def get_images_hashes(self):
        """Get image hashes"""
        # Searching for duplicates.
        for image in self.images:
            with img.open(image.img_path) as img:
                yield imagehash.average_hash(img, self.hash_size)

    def find_duplicates(self, img_path):
        """Find duplicates"""
        duplicates = []
        hashes = {}
        for temp_hash in self.get_images_hashes():
            if temp_hash in hashes:
                self.logger.info(
                    "Duplicate {} \nfound for image {}\n".format(
                        img_path, hashes[temp_hash]
                    )
                )
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
            if answer.strip().lower() == 'y':
                self.remove_duplicates(duplicates)
                self.logger.info('Duplicates images deleted successfully!')
        else:
            self.logger.info("No duplicates found")

    def diff(self, hash1, hash2):
        return np.count_nonzero(hash1 != hash2)

    def similarity(self, img_diff):
        threshold_img = img_diff / (self.hash_size ** 2)
        similarity_img = round((1 - threshold_img) * 100)

        return similarity_img

    def find_similar(self, image, similarity=80):
        """
        Find similar images
        :returns: img_path generator
        """
        hash1 = image.get_hash()

        if hash1 is None:
            return None

        self.logger.info(f'Finding similar images to {image.img_path}')

        threshold = 1 - similarity / 100
        diff_limit = int(threshold * (self.hash_size ** 2))

        for img in self.images:
            if not img.img_path.is_file():
                continue
            if img.img_path == image.img_path:
                continue
            hash2 = img.get_hash()
            # Be sure that hash are not None
            if hash2 is None:
                continue

            img_diff = self.diff(hash1, hash2)
            if img_diff <= diff_limit:
                similarity_img = self.similarity(img_diff)
                self.logger.info(
                    f'{img.img_path} image found {similarity_img}% similar to {image}'
                )
                yield img.img_path
