"""
Base :class:`Media` class for media objects that are tracked by Dozo.
The Media class provides some base functionality used by all the media types.
Sub-classes (:class:`~dozo.media.Audio`, :class:`~dozo.media.Photo`, and :class:`~dozo.media.Video`).
"""

import mimetypes
import os
import six
import logging

# load modules
from dateutil.parser import parse
import re
from dozo.exiftool import ExifToolCaching

class Media():

    """The media class for all media objects.

    :param str source: The fully qualified path to the video file.
    """

    __name__ = 'Media'

    d_coordinates = {
        'latitude': 'latitude_ref',
        'longitude': 'longitude_ref'
    }

    PHOTO = ('arw', 'cr2', 'dng', 'gif', 'heic', 'jpeg', 'jpg', 'nef', 'png', 'rw2')
    AUDIO = ('m4a',)
    VIDEO = ('avi', 'm4v', 'mov', 'mp4', 'mpg', 'mpeg', '3gp', 'mts')

    extensions = PHOTO + AUDIO + VIDEO


    def __init__(self, sources=None, ignore_tags=set()):
        self.source = sources
        self.reset_cache()
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
        self.date_modified = ['File:FileModifyDate', 'QuickTime:ModifyDate']
        self.camera_make_keys = ['EXIF:Make', 'QuickTime:Make']
        self.camera_model_keys = ['EXIF:Model', 'QuickTime:Model']
        self.album_keys = ['XMP-xmpDM:Album', 'XMP:Album']
        self.title_keys = ['XMP:Title', 'XMP:DisplayName']
        self.latitude_keys = [
            'EXIF:GPSLatitude',
            'XMP:GPSLatitude',
            # 'QuickTime:GPSLatitude',
            'Composite:GPSLatitude'
        ]
        self.longitude_keys = [
            'EXIF:GPSLongitude',
            'XMP:GPSLongitude',
            # 'QuickTime:GPSLongitude',
            'Composite:GPSLongitude'
        ]
        self.latitude_ref_key = 'EXIF:GPSLatitudeRef'
        self.longitude_ref_key = 'EXIF:GPSLongitudeRef'
        self.original_name_key = 'XMP:OriginalFileName'
        self.set_gps_ref = True
        self.metadata = None
        self.exif_metadata = None
        self.ignore_tags = ignore_tags


    def format_metadata(self, **kwargs):
        """Method to consistently return a populated metadata dictionary.

        :returns: dict
        """

    def get_file_path(self):
        """Get the full path to the video.

        :returns: string
        """
        return self.source


    def get_extension(self):
        """Get the file extension as a lowercased string.

        :returns: string or None for a non-video
        """
        if(not self.is_valid()):
            return None

        source = self.source
        return os.path.splitext(source)[1][1:]


    def get_metadata(self, update_cache=False, album_from_folder=False):
        """Get a dictionary of metadata for any file.

        All keys will be present and have a value of None if not obtained.

        :returns: dict or None for non-text files
        """
        if(not self.is_valid()):
            return None

        if(isinstance(self.metadata, dict) and update_cache is False):
            return self.metadata

        source = self.source
        folder = os.path.basename(os.path.dirname(source))
        album = self.get_album()
        if album_from_folder and (album is None or album == ''):
            album = folder

        self.metadata = {
            'date_original': self.get_date_attribute(self.date_original),
            'date_created': self.get_date_attribute(self.date_created),
            'date_modified': self.get_date_attribute(self.date_modified),
            'camera_make': self.get_camera_make(),
            'camera_model': self.get_camera_model(),
            'latitude': self.get_coordinate('latitude'),
            'longitude': self.get_coordinate('longitude'),
            'album': album,
            'title': self.get_title(),
            'mime_type': self.get_mimetype(),
            'original_name': self.get_original_name(),
            'base_name': os.path.basename(os.path.splitext(source)[0]),
            'ext': self.get_extension(),
            'directory_path': os.path.dirname(source)
        }

        return self.metadata


    def get_mimetype(self):
        """Get the mimetype of the file.

        :returns: str or None for unsupported files.
        """
        if(not self.is_valid()):
            return None

        source = self.source
        mimetype = mimetypes.guess_type(source)
        if(mimetype is None):
            return None

        return mimetype[0]


    def is_valid(self):
        # Disable extension check
        return True


    def set_album_from_folder(self, path):
        """Set the album attribute based on the leaf folder name

        :returns: bool
        """
        metadata = self.get_metadata()

        # If this file has an album already set we do not overwrite EXIF
        if(not isinstance(metadata, dict) or metadata['album'] is not None):
            return False

        folder = os.path.basename(metadata['directory_path'])
        # If folder is empty we skip
        if(len(folder) == 0):
            return False

        status = self.set_album(folder, path)
        if status == False:
            return False
        return True


    def set_metadata_basename(self, new_basename):
        """Update the basename attribute in the metadata dict for this instance.

        This is used for when we update the EXIF title of a media file. Since
        that determines the name of a file if we update the title of a file
        more than once it appends to the file name.

        i.e. 2015-12-31_00-00-00-my-first-title-my-second-title.jpg

        :param str new_basename: New basename of file (with the old title
            removed).
        """
        self.get_metadata()
        self.metadata['base_name'] = new_basename


    def set_metadata(self, **kwargs):
        """Method to manually update attributes in metadata.

        :params dict kwargs: Named parameters to update.
        """
        metadata = self.get_metadata()
        for key in kwargs:
            if(key in metadata):
                self.metadata[key] = kwargs[key]


    @classmethod
    def get_class_by_file(cls, _file, classes, ignore_tags=set()):
        """Static method to get a media object by file.
        """
        basestring = (bytes, str)
        if not isinstance(_file, basestring) or not os.path.isfile(_file):
            return None

        extension = os.path.splitext(_file)[1][1:].lower()

        if len(extension) > 0:
            for i in classes:
                if(extension in i.extensions):
                    return i(_file, ignore_tags=ignore_tags)

        exclude_list = ['.DS_Store', '.directory']
        if os.path.basename(_file) == '.DS_Store':
            return None
        else:
            return Media(_file, ignore_tags=ignore_tags)


    @classmethod
    def get_valid_extensions(cls):
        """Static method to access static extensions variable.

        :returns: tuple(str)
        """
        return cls.extensions


    def get_album(self):
        """Get album from EXIF

        :returns: None or string
        """
        if(not self.is_valid()):
            return None

        exiftool_attributes = self.get_exiftool_attributes()
        if exiftool_attributes is None:
            return None

        for album_key in self.album_keys:
            if album_key in exiftool_attributes:
                return exiftool_attributes[album_key]

        return None


    def get_coordinate(self, type='latitude'):
        """Get latitude or longitude of media from EXIF

        :param str type: Type of coordinate to get. Either "latitude" or
            "longitude".
        :returns: float or None if not present in EXIF or a non-photo file
        """

        exif = self.get_exiftool_attributes()
        if not exif:
            return None

        # The lat/lon _keys array has an order of precedence.
        # The first key is writable and we will give the writable
        #   key precence when reading.
        direction_multiplier = 1.0
        for key in self.latitude_keys + self.longitude_keys:
            if key not in exif:
                continue
            if isinstance(exif[key], six.string_types) and len(exif[key]) == 0:
                # If exiftool GPS output is empty, the data returned will be a str
                # with 0 length.
                # https://github.com/jmathai/elodie/issues/354
                continue

            # Cast coordinate to a float due to a bug in exiftool's
            #   -json output format.
            # https://github.com/jmathai/elodie/issues/171
            # http://u88.n24.queensu.ca/exiftool/forum/index.php/topic,7952.0.html  # noqa
            this_coordinate = float(exif[key])

            # TODO: verify that we need to check ref key
            #   when self.set_gps_ref != True
            if type == 'latitude' and key in self.latitude_keys:
                if self.latitude_ref_key in exif and \
                        exif[self.latitude_ref_key] == 'S':
                    direction_multiplier = -1.0
                return this_coordinate * direction_multiplier
            elif type == 'longitude' and key in self.longitude_keys:
                if self.longitude_ref_key in exif and \
                        exif[self.longitude_ref_key] == 'W':
                    direction_multiplier = -1.0
                return this_coordinate * direction_multiplier

        return None


    def get_exiftool_attributes(self):
        """Get attributes for the media object from exiftool.

        :returns: dict, or False if exiftool was not available.
        """
        source = self.source

        #Cache exif metadata results and use if already exists for media
        if(self.exif_metadata is None):
            self.exif_metadata = ExifToolCaching(source, logger=self.logger).asdict()
            for tag_regex in self.ignore_tags:
                ignored_tags = set()
                for tag in self.exif_metadata:
                    if re.search(tag_regex, tag) is not None:
                        ignored_tags.add(tag)
                for ignored_tag in ignored_tags:
                    del self.exif_metadata[ignored_tag]


        if not self.exif_metadata:
            return False

        return self.exif_metadata


    def get_date_attribute(self, tag):
        """Get a date attribute.
        :returns: time object or None
        """
        exif = self.get_exiftool_attributes()
        if not exif:
            return None
        # We need to parse a string from EXIF into a timestamp.
        # EXIF DateTimeOriginal and EXIF DateTime are both stored
        #   in %Y:%m:%d %H:%M:%S format
        # we split on a space and then r':|-' -> convert to int -> .timetuple()
        #   the conversion in the local timezone
        # EXIF DateTime is already stored as a timestamp
        # Sourced from https://github.com/photo/frontend/blob/master/src/libraries/models/Photo.php#L500  # noqa
        for key in tag:
            try:
                if(key in exif):
                    # correct nasty formated date
                    regex = re.compile('(\d{4}):(\d{2}):(\d{2})')
                    if(re.match(regex , exif[key]) is not None):  # noqa
                        exif[key] = re.sub(regex ,'\g<1>-\g<2>-\g<3>',exif[key])
                    return parse(exif[key])
                    # if(re.match('\d{4}(-|:)\d{2}(-|:)\d{2}', exif[key]) is not None):  # noqa
                    #     dt, tm = exif[key].split(' ')
                    #     dt_list = compile(r'-|:').split(dt)
                    #     dt_list = dt_list + compile(r'-|:').split(tm)
                    #     dt_list = map(int, dt_list)
                    #     return datetime(*dt_list)
            except BaseException  or dateutil.parser._parser.ParserError as e:
                log.error(e)
                return None

        return None


    def get_camera_make(self):
        """Get the camera make stored in EXIF.

        :returns: str
        """
        if(not self.is_valid()):
            return None

        exiftool_attributes = self.get_exiftool_attributes()

        if exiftool_attributes is None:
            return None

        for camera_make_key in self.camera_make_keys:
            if camera_make_key in exiftool_attributes:
                return exiftool_attributes[camera_make_key]

        return None


    def get_camera_model(self):
        """Get the camera make stored in EXIF.

        :returns: str
        """
        if(not self.is_valid()):
            return None

        exiftool_attributes = self.get_exiftool_attributes()

        if exiftool_attributes is None:
            return None

        for camera_model_key in self.camera_model_keys:
            if camera_model_key in exiftool_attributes:
                return exiftool_attributes[camera_model_key]

        return None


    def get_original_name(self):
        """Get the original name stored in EXIF.

        :returns: str
        """
        if(not self.is_valid()):
            return None

        exiftool_attributes = self.get_exiftool_attributes()

        if exiftool_attributes is None:
            return None

        if(self.original_name_key not in exiftool_attributes):
            return None

        return exiftool_attributes[self.original_name_key]


    def get_title(self):
        """Get the title for a photo of video

        :returns: str or None if no title is set or not a valid media type
        """
        if(not self.is_valid()):
            return None

        exiftool_attributes = self.get_exiftool_attributes()

        if exiftool_attributes is None:
            return None

        for title_key in self.title_keys:
            if title_key in exiftool_attributes:
                return exiftool_attributes[title_key]

        return None


    def reset_cache(self):
        """Resets any internal cache
        """
        self.exiftool_attributes = None
        self.exif_metadata = None


    def set_album(self, name, path):
        """Set album EXIF tag if not already set.

        :returns: True, False, None
        """
        if self.get_album() is not None:
            return None

        tags = {}
        for key in self.album_keys:
            tags[key] = name
        status = self.__set_tags(tags, path)
        self.reset_cache()

        return status


    def set_date_original(self, time, path):
        """Set the date/time a photo was taken.

        :param datetime time: datetime object of when the photo was taken
        :returns: bool
        """
        if(time is None):
            return False

        tags = {}
        formatted_time = time.strftime('%Y:%m:%d %H:%M:%S')
        for key in self.date_original:
            tags[key] = formatted_time

        status = self.__set_tags(tags, path)
        if status == False:
            # exif attribute date_original d'ont exist
            for key in self.date_created:
                tags[key] = formatted_time

            status = self.__set_tags(tags, path)
        self.reset_cache()
        return status


    def set_location(self, latitude, longitude, path):
        if(not self.is_valid()):
            return None

        # The lat/lon _keys array has an order of precedence.
        # The first key is writable and we will give the writable
        #   key precence when reading.
        # TODO check
        # tags = {
        #     self.latitude_keys[0]: latitude,
        #     self.longitude_keys[0]: longitude,
        # }
        tags = {}
        for key in self.latitude_keys:
            tags[key] = latitude
        for key in self.longitude_keys:
            tags[key] = longitude

        # If self.set_gps_ref == True then it means we are writing an EXIF
        #   GPS tag which requires us to set the reference key.
        # That's because the lat/lon are absolute values.
        # TODO set_gps_ref = False for Video ?
        if self.set_gps_ref:
            if latitude < 0:
                tags[self.latitude_ref_key] = 'S'

            if longitude < 0:
                tags[self.longitude_ref_key] = 'W'

        status = self.__set_tags(tags, path)
        self.reset_cache()

        return status


    def set_original_name(self, path, name=None):
        """Sets the original name EXIF tag if not already set.

        :returns: True, False, None
        """
        # If EXIF original name tag is set then we return.
        if self.get_original_name() is not None:
            return None

        if name == None:
            name = os.path.basename(self.source)

        tags = {self.original_name_key: name}
        status = self.__set_tags(tags, path)
        self.reset_cache()

        return status


    def set_title(self, title, path):
        """Set title for a photo.

        :param str title: Title of the photo.
        :returns: bool
        """
        if(not self.is_valid()):
            return None

        if(title is None):
            return None

        tags = {}
        for key in self.title_keys:
            tags[key] = title
        status = self.__set_tags(tags, path)
        self.reset_cache()

        return status


    def __set_tags(self, tags, path):
        if(not self.is_valid()):
            return None

        status = ''
        for tag, value in tags.items():
            status = ExifToolCaching(path, self.logger).setvalue(tag, value)
        if status.decode().find('unchanged') != -1 or status == '':
            return False
        if status.decode().find('error') != -1:
            return False

        return True


def get_all_subclasses(cls=None):
    """Module method to get all subclasses of Media.
    """
    subclasses = set()

    this_class = Media
    if cls is not None:
        this_class = cls

    subclasses.add(this_class)

    this_class_subclasses = this_class.__subclasses__()
    for child_class in this_class_subclasses:
        subclasses.update(get_all_subclasses(child_class))

    return subclasses


def get_media_class(_file, ignore_tags=set()):
    if not os.path.exists(_file):
        logging.warning(f'Could not find {_file}')
        logging.error(f'Could not find {_file}')
        return False

    media = Media.get_class_by_file(_file, get_all_subclasses(), ignore_tags=set())
    if not media:
        logging.warning(f'File{_file} is not supported')
        logging.error(f'File {_file} can\'t be imported')
        return False

    return media

