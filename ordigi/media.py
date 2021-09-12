"""
Media :class:`Media` class to get file metadata
"""

import logging
import mimetypes
import os

# load modules
from dateutil.parser import parse
import re
from ordigi.exiftool import ExifTool, ExifToolCaching
from ordigi.utils import get_date_from_string

class Media():

    """The media class for all media objects.

    :param str file_path: The fully qualified path to the media file.
    """

    d_coordinates = {
        'latitude': 'latitude_ref',
        'longitude': 'longitude_ref'
    }

    PHOTO = ('arw', 'cr2', 'dng', 'gif', 'heic', 'jpeg', 'jpg', 'nef', 'png', 'rw2')
    AUDIO = ('m4a',)
    VIDEO = ('avi', 'm4v', 'mov', 'mp4', 'mpg', 'mpeg', '3gp', 'mts')

    extensions = PHOTO + AUDIO + VIDEO

    def __init__(self, path, subdirs, filename, album_from_folder=False, ignore_tags=set(),
            interactive=False, logger=logging.getLogger()):
        self.path = path
        self.subdirs = subdirs
        self.filename = filename
        self.file_path = os.path.join(path, subdirs, filename)

        self.album_from_folder = album_from_folder
        self.ignore_tags = ignore_tags
        self.tags_keys = self.get_tags()
        self.exif_metadata = None
        self.interactive = interactive
        self.metadata = None
        self.logger = logger

    def get_tags(self):
        tags_keys = {}
        tags_keys['date_original'] = [
            'EXIF:DateTimeOriginal',
            'H264:DateTimeOriginal',
            'QuickTime:ContentCreateDate'
        ]
        tags_keys['date_created'] = [
            'EXIF:CreateDate',
            'QuickTime:CreationDate',
            'QuickTime:CreateDate',
            'QuickTime:CreationDate-und-US',
            'QuickTime:MediaCreateDate'
        ]
        tags_keys['date_modified'] = [
            'File:FileModifyDate',
            'QuickTime:ModifyDate'
        ]
        tags_keys['camera_make'] = ['EXIF:Make', 'QuickTime:Make']
        tags_keys['camera_model'] = ['EXIF:Model', 'QuickTime:Model']
        tags_keys['album'] = ['XMP-xmpDM:Album', 'XMP:Album']
        tags_keys['title'] = ['XMP:Title', 'XMP:DisplayName']
        tags_keys['latitude'] = [
            'EXIF:GPSLatitude',
            'XMP:GPSLatitude',
            # 'QuickTime:GPSLatitude',
            'Composite:GPSLatitude'
        ]
        tags_keys['longitude'] = [
            'EXIF:GPSLongitude',
            'XMP:GPSLongitude',
            # 'QuickTime:GPSLongitude',
            'Composite:GPSLongitude'
        ]
        tags_keys['latitude_ref'] = ['EXIF:GPSLatitudeRef']
        tags_keys['longitude_ref'] = ['EXIF:GPSLongitudeRef']
        tags_keys['original_name'] = ['XMP:OriginalFileName']

        # Remove ignored tag from list
        for tag_regex in self.ignore_tags:
            ignored_tags = set()
            for key, tags in tags_keys.items():
                for n, tag in enumerate(tags):
                    if re.match(tag_regex, tag):
                        del(tags_keys[key][n])

        return tags_keys

    def _del_ignored_tags(self, exif_metadata):
        for tag_regex in self.ignore_tags:
            ignored_tags = set()
            for tag in exif_metadata:
                if re.search(tag_regex, tag) is not None:
                    ignored_tags.add(tag)
            for ignored_tag in ignored_tags:
                del exif_metadata[ignored_tag]

    def get_mimetype(self):
        """Get the mimetype of the file.

        :returns: str or None
        """
        mimetype = mimetypes.guess_type(self.file_path)
        if(mimetype is None):
            return None

        return mimetype[0]

    def _get_key_values(self, key):
        """Get the first value of a tag set

        :returns: str or None if no exif tag
        """
        if self.exif_metadata is None:
            return None

        for tag in self.tags_keys[key]:
            if tag in self.exif_metadata:
                yield self.exif_metadata[tag]

    def get_value(self, tag):
        """Get given value from EXIF.

        :returns: str or None
        """
        if self.exif_metadata is None:
            return None
        if(tag not in self.exif_metadata):
            return None

        return self.exif_metadata[tag]

    def get_date_format(self, value):
        """Formate date attribute.
        :returns: datetime object or None
        """
        # We need to parse a string to datetime format.
        # EXIF DateTimeOriginal and EXIF DateTime are both stored
        #   in %Y:%m:%d %H:%M:%S format
        if value is None:
            return None

        try:
            # correct nasty formated date
            regex = re.compile(r'(\d{4}):(\d{2}):(\d{2})')
            if(re.match(regex , value) is not None):  # noqa
                value = re.sub(regex , r'\g<1>-\g<2>-\g<3>', value)
            return parse(value)
        except BaseException  or dateutil.parser._parser.ParserError as e:
            self.logger.warning(e.args, value)
            return None

    def get_coordinates(self, key, value):
        """Get latitude or longitude value

        :param str key: Type of coordinate to get. Either "latitude" or
            "longitude".
        :returns: float or None
        """
        if value is None:
            return None

        if isinstance(value, str) and len(value) == 0:
            # If exiftool GPS output is empty, the data returned will be a str
            # with 0 length.
            # https://github.com/jmathai/elodie/issues/354
            return None

        # Cast coordinate to a float due to a bug in exiftool's
        #   -json output format.
        # https://github.com/jmathai/elodie/issues/171
        # http://u88.n24.queensu.ca/exiftool/forum/index.php/topic,7952.0.html  # noqa
        this_coordinate = float(value)

        direction_multiplier = 1.0
        #   when self.set_gps_ref != True
        if key == 'latitude':
            if 'EXIF:GPSLatitudeRef' in self.exif_metadata:
                if self.exif_metadata['EXIF:GPSLatitudeRef'] == 'S':
                    direction_multiplier = -1.0
        elif key == 'longitude':
            if 'EXIF:GPSLongitudeRef' in self.exif_metadata:
                if self.exif_metadata['EXIF:GPSLongitudeRef'] == 'W':
                    direction_multiplier = -1.0
        return this_coordinate * direction_multiplier

        return None

    def get_date_taken(self):
        '''
        Get the date taken from self.metadata or filename
        :returns: datetime or None.
        '''
        if self.metadata is None:
            return None

        basename = os.path.splitext(self.metadata['filename'])[0]
        date_original = self.metadata['date_original']
        if self.metadata['original_name'] is not  None:
            date_filename = get_date_from_string(self.metadata['original_name'])
        else:
            date_filename = get_date_from_string(basename)

        date_created = self.metadata['date_created']
        if self.metadata['date_original'] is not None:
            if (date_filename is not None and
                    date_filename != date_original):
                self.logger.warn(f"{basename} time mark is different from {date_original}")
                # TODO ask for keep date taken, filename time, or neither
            return self.metadata['date_original']
        elif True:
            if date_filename is not  None:
                if date_created is not None and date_filename > date_created:
                    self.logger.warn(f"{basename} time mark is more recent than {date_created}")
                return date_filename
        if True:
            # TODO warm and ask for confirmation
            if date_created is not  None:
                return date_created
            elif self.metadata['date_modified'] is not  None:
                return self.metadata['date_modified']

    def get_exif_metadata(self):
        # Get metadata from exiftool.
        self.exif_metadata = ExifToolCaching(self.file_path, logger=self.logger).asdict()

    def get_metadata(self, loc=None, db=None, cache=False):
        """Get a dictionary of metadata from exif.
        All keys will be present and have a value of None if not obtained.

        :returns: dict
        """
        self.get_exif_metadata()

        self.metadata = {}
        # Retrieve selected metadata to dict
        if not self.exif_metadata:
            return self.metadata

        for key in self.tags_keys:
            formated_data = None
            for value in self._get_key_values(key):
                if 'date' in key:
                    formated_data = self.get_date_format(value)
                elif key in ('latitude', 'longitude'):
                    formated_data = self.get_coordinates(key, value)
                else:
                    if value is not None and value != '':
                        formated_data = value
                    else:
                        formated_data = None
                if formated_data:
                    # Use this data and break
                    break

            self.metadata[key] = formated_data

        self.metadata['src_path']  = self.path
        self.metadata['subdirs']  = self.subdirs
        self.metadata['filename']  = self.filename
        self.metadata['date_taken']  = self.get_date_taken()

        if self.album_from_folder:
            album = self.metadata['album']
            folder = os.path.basename(self.subdirs)
            if  album and album != '':
                if self.interactive:
                    print(f"Conflict for file: {self.file_path}")
                    print(f"Exif album is already set to '{album}'', folder='{folder}'")
                    i = f"Choice for 'album': (a) '{album}', (f) '{folder}', (c) custom ?\n"
                    answer = input(i)
                    if answer == 'c':
                        self.metadata['album'] = input('album=')
                        self.set_value('album', folder)
                    if answer == 'a':
                        self.metadata['album'] = album
                    elif answer == 'f':
                        self.metadata['album'] = folder

            if  not album or album == '':
                self.metadata['album'] = folder

        loc_keys = ('latitude', 'longitude', 'city', 'state', 'country', 'default')
        location_id = None
        if cache and db:
            location_id = db.get_metadata_data(self.file_path, 'LocationId')

        if location_id:
            for key in loc_keys:
                # use str to convert non string format data like latitude and
                # longitude
                self.metadata[key] = str(db.get_location(location_id, key.capitalize()))
        elif loc:
            place_name = loc.place_name(
                self.metadata['latitude'],
                self.metadata['longitude'],
                self.logger
            )
            for key in ('city', 'state', 'country', 'default'):
                # mask = 'city'
                # place_name = {'default': u'Sunnyvale', 'city-random': u'Sunnyvale'}
                if(key in place_name):
                    self.metadata[key] = place_name[key]
                else:
                    self.metadata[key] = None

        else:
            for key in loc_keys:
                self.metadata[key] = None

        self.metadata['location_id'] = location_id

        return self.metadata

    def has_exif_data(self):
        """Check if file has metadata, date original"""
        if not self.metadata:
            return False

        if 'date_original' in self.metadata:
            if self.metadata['date_original'] != None:
                return True

        return False

    @classmethod
    def get_class_by_file(cls, _file, classes, ignore_tags=set(), logger=logging.getLogger()):
        """Static method to get a media object by file.
        """
        if not os.path.isfile(_file):
            return None

        extension = os.path.splitext(_file)[1][1:].lower()

        if len(extension) > 0:
            for i in classes:
                if(extension in i.extensions):
                    return i(_file, ignore_tags=ignore_tags, logger=logger)

        return Media(_file, logger, ignore_tags=ignore_tags, logger=logger)

    def set_value(self, tag, value):
        """Set value of a tag.

        :returns: value (str)
        """
        return ExifTool(self.file_path, self.logger).setvalue(tag, value)

    def set_date_taken(self, date_key, time):
        """Set the date/time a photo was taken.

        :param datetime time: datetime object of when the photo was taken
        :returns: bool
        """
        if(time is None):
            return False

        formatted_time = time.strftime('%Y:%m:%d %H:%M:%S')
        status = self.set_value('date_original', formatted_time)
        if status == False:
            # exif attribute date_original d'ont exist
            status = self.set_value('date_created', formatted_time)

        return status

    def set_coordinates(self, latitude, longitude):
        status = []
        if self.metadata['latitude_ref']:
            latitude = abs(latitude)
            if latitude > 0:
                status.append(self.set_value('latitude_ref', 'N'))
            else:
                status.append(self.set_value('latitude_ref', 'S'))

        status.append(self.set_value('latitude', latitude))

        if  self.metadata['longitude_ref']:
            longitude = abs(longitude)
            if longitude > 0:
                status.append(self.set_value('latitude_ref', 'E'))
            else:
                status.append(self.set_value('longitude_ref', 'W'))

        status.append(self.set_value('longitude', longitude))

        if all(status):
            return True
        else:
            return False

    def set_album_from_folder(self):
        """Set the album attribute based on the leaf folder name

        :returns: bool
        """
        folder = os.path.basename(os.path.dirname(self.file_path))

        return self.set_value('album', folder)


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


def get_media_class(_file, ignore_tags=set(), logger=logging.getLogger()):
    if not os.path.exists(_file):
        logger.warning(f'Could not find {_file}')
        logger.error(f'Could not find {_file}')
        return False

    media = Media.get_class_by_file(_file, get_all_subclasses(),
            ignore_tags=set(), logger=logger)
    if not media:
        logger.warning(f'File{_file} is not supported')
        logger.error(f'File {_file} can\'t be imported')
        return False

    return media

