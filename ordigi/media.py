"""
Media :class:`Media` class to get file metadata
"""

import logging
import mimetypes
import os
import re
import sys

from dateutil import parser
import inquirer

from ordigi.exiftool import ExifTool, ExifToolCaching
from ordigi import utils
from ordigi import request


class Metadata:

    def __init__(self, ignore_tags=None):

        # Options
        if ignore_tags is None:
            ignore_tags = set()

        self.exif_metadata = []
        self.metadata = {}
        # self.datas = {}
        self.ignore_tags = ignore_tags

        # Attributes
        self.tags_keys = self.get_tags()

    def get_tags(self) -> dict:
        """Get exif tags groups in dict"""
        tags_keys = {}
        tags_keys['date_original'] = [
            'EXIF:DateTimeOriginal',
            'H264:DateTimeOriginal',
            'QuickTime:ContentCreateDate',
        ]
        tags_keys['date_created'] = [
            'EXIF:CreateDate',
            'QuickTime:CreationDate',
            'QuickTime:CreateDate',
            'QuickTime:CreationDate-und-US',
            'QuickTime:MediaCreateDate',
        ]
        tags_keys['date_modified'] = ['File:FileModifyDate', 'QuickTime:ModifyDate']
        tags_keys['camera_make'] = ['EXIF:Make', 'QuickTime:Make']
        tags_keys['camera_model'] = ['EXIF:Model', 'QuickTime:Model']
        tags_keys['album'] = ['XMP-xmpDM:Album', 'XMP:Album']
        tags_keys['title'] = ['XMP:Title', 'XMP:DisplayName']
        tags_keys['latitude'] = [
            'EXIF:GPSLatitude',
            'XMP:GPSLatitude',
            # 'QuickTime:GPSLatitude',
            'Composite:GPSLatitude',
        ]
        tags_keys['longitude'] = [
            'EXIF:GPSLongitude',
            'XMP:GPSLongitude',
            # 'QuickTime:GPSLongitude',
            'Composite:GPSLongitude',
        ]
        tags_keys['latitude_ref'] = ['EXIF:GPSLatitudeRef']
        tags_keys['longitude_ref'] = ['EXIF:GPSLongitudeRef']
        tags_keys['original_name'] = ['XMP:OriginalFileName']

        # Remove ignored tag from list
        for tag_regex in self.ignore_tags:
            for key, tags in tags_keys.items():
                for i, tag in enumerate(tags):
                    if re.match(tag_regex, tag):
                        del tags_keys[key][i]

        return tags_keys

    def _del_ignored_tags(self):
        for tag_regex in self.ignore_tags:
            ignored_tags = set()
            for tag in self.exif_metadata:
                if re.search(tag_regex, tag) is not None:
                    ignored_tags.add(tag)
            for ignored_tag in ignored_tags:
                del self.exif_metadata[ignored_tag]

class WriteExif(Metadata):

    def __init__(
            self,
            file_path,
            metadata,
            exif_metadata=None,
            ignore_tags=None,
            logger=logging.getLogger(),
            ):
        super().__init__(ignore_tags)
        self.file_path = file_path
        self.metadata = metadata

        if not exif_metadata:
            exif_metadata = []

        self.exif_metadata = exif_metadata
        self.logger = logger.getChild(self.__class__.__name__)

    def set_value(self, tag, value):
        """Set value of a tag.

        :returns: value (str)
        """
        return ExifTool(self.file_path, logger=self.logger).setvalue(tag, value)

    def set_key_values(self, key, value):
        """Set tags values for given key"""
        status = True
        if self.exif_metadata is None:
            return False

        for tag in self.tags_keys[key]:
            if tag in self.exif_metadata:
                if not self.set_value(tag, value):
                    status = False

        return status

    def set_date_media(self, time):
        """
        Set the date/time a photo was taken.
        :param datetime time: datetime object of when the photo was taken
        :returns: bool
        """
        if time is None:
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

        if self.metadata['longitude_ref']:
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
        return self.set_value('album', self.file_path.parent.name)


class ReadExif(Metadata):
    def __init__(
        self,
        file_path,
        src_dir,
        album_from_folder=False,
        ignore_tags=None,
        interactive=False,
        logger=logging.getLogger(),
        use_date_filename=False,
        use_file_dates=False,
    ):
        super().__init__(ignore_tags)



class Media:
    """
    Extract matadatas from exiftool and sort them to dict structure
    """

    d_coordinates = {'latitude': 'latitude_ref', 'longitude': 'longitude_ref'}

    PHOTO = ('arw', 'cr2', 'dng', 'gif', 'heic', 'jpeg', 'jpg', 'nef', 'png', 'rw2')
    AUDIO = ('m4a',)
    VIDEO = ('avi', 'm4v', 'mov', 'mp4', 'mpg', 'mpeg', '3gp', 'mts')

    extensions = PHOTO + AUDIO + VIDEO

    def __init__(
        self,
        file_path,
        src_dir,
        album_from_folder=False,
        ignore_tags=None,
        interactive=False,
        logger=logging.getLogger(),
        use_date_filename=False,
        use_file_dates=False,
    ):
        """
        :params: Path, Path, bool, set, bool, Logger
        """
        self.file_path = file_path
        self.src_dir = src_dir

        self.album_from_folder = album_from_folder
        self.exif_metadata = None

        if ignore_tags is None:
            ignore_tags = set()
        self.ignore_tags = ignore_tags
        self.interactive = interactive
        self.logger = logger.getChild(self.__class__.__name__)
        self.metadata = None
        self.tags_keys = self.get_tags()
        self.use_date_filename = use_date_filename
        self.use_file_dates = use_file_dates

        self.theme = request.load_theme()

    def get_tags(self) -> dict:
        """Get exif tags groups in dict"""
        tags_keys = {}
        tags_keys['date_original'] = [
            'EXIF:DateTimeOriginal',
            'H264:DateTimeOriginal',
            'QuickTime:ContentCreateDate',
        ]
        tags_keys['date_created'] = [
            'EXIF:CreateDate',
            'QuickTime:CreationDate',
            'QuickTime:CreateDate',
            'QuickTime:CreationDate-und-US',
            'QuickTime:MediaCreateDate',
        ]
        tags_keys['date_modified'] = ['File:FileModifyDate', 'QuickTime:ModifyDate']
        tags_keys['camera_make'] = ['EXIF:Make', 'QuickTime:Make']
        tags_keys['camera_model'] = ['EXIF:Model', 'QuickTime:Model']
        tags_keys['album'] = ['XMP-xmpDM:Album', 'XMP:Album']
        tags_keys['title'] = ['XMP:Title', 'XMP:DisplayName']
        tags_keys['latitude'] = [
            'EXIF:GPSLatitude',
            'XMP:GPSLatitude',
            # 'QuickTime:GPSLatitude',
            'Composite:GPSLatitude',
        ]
        tags_keys['longitude'] = [
            'EXIF:GPSLongitude',
            'XMP:GPSLongitude',
            # 'QuickTime:GPSLongitude',
            'Composite:GPSLongitude',
        ]
        tags_keys['latitude_ref'] = ['EXIF:GPSLatitudeRef']
        tags_keys['longitude_ref'] = ['EXIF:GPSLongitudeRef']
        tags_keys['original_name'] = ['XMP:OriginalFileName']

        # Remove ignored tag from list
        for tag_regex in self.ignore_tags:
            for key, tags in tags_keys.items():
                for i, tag in enumerate(tags):
                    if re.match(tag_regex, tag):
                        del tags_keys[key][i]

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
        if mimetype is None:
            return None

        return mimetype[0]

    def _get_key_values(self, key):
        """
        Get the first value of a tag set
        :returns: str or None if no exif tag
        """
        if self.exif_metadata is None:
            return None

        for tag in self.tags_keys[key]:
            if tag in self.exif_metadata:
                yield self.exif_metadata[tag]

    def get_value(self, tag):
        """
        Get given value from EXIF.
        :returns: str or None
        """
        if self.exif_metadata is None:
            return None
        if tag not in self.exif_metadata:
            return None

        return self.exif_metadata[tag]

    def get_date_format(self, value):
        """Formatting date attribute.
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
            if re.match(regex, value) is not None:  # noqa
                value = re.sub(regex, r'\g<1>-\g<2>-\g<3>', value)
            return parser.parse(value)
        except BaseException or parser._parser.ParserError as e:
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

    def _get_date_media_interactive(self, choices, default):
        print(f"Date conflict for file: {self.file_path}")
        choices_list = [
            inquirer.List(
                'date_list',
                message=f"Choice appropriate original date",
                choices=choices,
                default=default,
            ),
        ]
        answers = inquirer.prompt(choices_list, theme=self.theme)

        if not answers['date_list']:
            prompt = [
                inquirer.Text('date_custom', message="date"),
            ]
            answers = inquirer.prompt(prompt, theme=self.theme)
            return self.get_date_format(answers['date_custom'])
        else:
            return answers['date_list']

    def get_date_media(self):
        '''
        Get the date taken from self.metadata or filename
        :returns: datetime or None.
        '''
        if self.metadata is None:
            return None

        filename = self.metadata['filename']
        stem = os.path.splitext(filename)[0]
        date_original = self.metadata['date_original']
        if self.metadata['original_name']:
            date_filename = self.get_date_format(self.metadata['original_name'])
        else:
            date_filename = self.get_date_format(stem)

        date_original = self.metadata['date_original']
        date_created = self.metadata['date_created']
        date_modified = self.metadata['date_modified']
        if self.metadata['date_original']:
            if date_filename and date_filename != date_original:
                self.logger.warning(
                    f"{filename} time mark is different from {date_original}"
                )
                if self.interactive:
                    # Ask for keep date taken, filename time, or neither
                    choices = [
                        (f"date original:'{date_original}'", date_original),
                        (f"date filename:'{date_filename}'", date_filename),
                        ("custom", None),
                    ]
                    default = f'{date_original}'
                    return self._get_date_media_interactive(choices, default)

            return self.metadata['date_original']

        self.logger.warning(f"could not find original date for {self.file_path}")

        if self.use_date_filename and date_filename:
            self.logger.info(
                f"use date from filename:{date_filename} for {self.file_path}"
            )
            if date_created and date_filename > date_created:
                self.logger.warning(
                    f"{filename} time mark is more recent than {date_created}"
                )
                if self.interactive:
                    choices = [
                        (f"date filename:'{date_filename}'", date_filename),
                        (f"date created:'{date_created}'", date_created),
                        ("custom", None),
                    ]
                    default = date_filename
                    return self._get_date_media_interactive(choices, default)

            return date_filename

        elif self.use_file_dates:
            if date_created:
                self.logger.warning(
                    f"use date created:{date_created} for {self.file_path}"
                )
                return date_created
            elif date_modified:
                self.logger.warning(
                    f"use date modified:{date_modified} for {self.file_path}"
                )
                return date_modified
        elif self.interactive:
            choices = []
            if date_filename:
                choices.append((f"date filename:'{date_filename}'", date_filename))
            if date_created:
                choices.append((f"date created:'{date_created}'", date_created))
            if date_modified:
                choices.append((f"date modified:'{date_modified}'", date_modified))
            choices.append(("custom", None))
            default = date_filename
            return self._get_date_media_interactive(choices, default)

    def get_exif_metadata(self):
        # Get metadata from exiftool.
        self.exif_metadata = ExifToolCaching(
            self.file_path, logger=self.logger
        ).asdict()

    def _set_album(self, album, folder):
        print(f"Metadata conflict for file: {self.file_path}")
        choices_list = [
            inquirer.List(
                'album',
                message=f"Exif album is already set to {album}, choices",
                choices=[
                    (f"album:'{album}'", album),
                    (f"folder:'{folder}'", folder),
                    ("custom", None),
                ],
                default=f'{album}',
            ),
        ]
        prompt = [
            inquirer.Text('custom', message="album"),
        ]

        answers = inquirer.prompt(choices_list, theme=self.theme)
        if not answers['album']:
            answers = inquirer.prompt(prompt, theme=self.theme)
            return answers['custom']
        else:
            return answers['album']

    def _set_metadata_from_exif(self):

        self.metadata['src_dir'] = str(self.src_dir)
        self.metadata['subdirs'] = str(
            self.file_path.relative_to(self.src_dir).parent
        )
        self.metadata['filename'] = self.file_path.name
        # Get metadata from exif

        self.get_exif_metadata()

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

    def _set_metadata_from_db(self, db, relpath):
        # Get metadata from db
        formated_data = None
        for key in self.tags_keys:
            if key in (
                'latitude',
                'longitude',
                'latitude_ref',
                'longitude_ref',
                'file_path',
            ):
                continue

            label = utils.snake2camel(key)
            value = db.get_metadata_data(relpath, label)
            if 'date' in key:
                formated_data = self.get_date_format(value)
            else:
                formated_data = value
            self.metadata[key] = formated_data
        for key in 'src_dir', 'subdirs', 'filename':
            label = utils.snake2camel(key)
            formated_data = db.get_metadata_data(relpath, label)
            self.metadata[key] = formated_data

        return db.get_metadata_data(relpath, 'LocationId')

    def _check_file(self, db, root):
        # Check if file_path is a subpath of root
        if str(self.file_path).startswith(str(root)):
            relpath = os.path.relpath(self.file_path, root)
            db_checksum = db.get_checksum(relpath)
            file_checksum = self.metadata['checksum']
            # Check if checksum match
            if db_checksum and db_checksum != file_checksum:
                self.logger.error(f'{self.file_path} checksum has changed')
                self.logger.error('(modified or corrupted file).')
                self.logger.error(
                    f'file_checksum={file_checksum},\ndb_checksum={db_checksum}'
                )
                self.logger.info(
                    'Use --reset-cache, check database integrity or try to restore the file'
                )
                # We d'ont want to silently ignore or correct this without
                # resetting the cache as is could be due to file corruption
                sys.exit(1)

            return relpath, db_checksum

        return

    def _set_location_metadata(self, location_id, db, loc=None):

        self.metadata['location_id'] = location_id

        loc_keys = (
            'latitude',
            'longitude',
            'latitude_ref',
            'longitude_ref',
            'city',
            'state',
            'country',
            'default',
        )

        if location_id:
            for key in loc_keys:
                # use str to convert non string format data like latitude and
                # longitude
                self.metadata[key] = str(
                    db.get_location_data(location_id, utils.snake2camel(key))
                )
        elif loc:
            for key in 'latitude', 'longitude', 'latitude_ref', 'longitude_ref':
                self.metadata[key] = None

            place_name = loc.place_name(
                self.metadata['latitude'], self.metadata['longitude']
            )
            for key in ('city', 'state', 'country', 'default'):
                # mask = 'city'
                # place_name = {'default': u'Sunnyvale', 'city-random': u'Sunnyvale'}
                if key in place_name:
                    self.metadata[key] = place_name[key]
                else:
                    self.metadata[key] = None

        else:
            for key in loc_keys:
                self.metadata[key] = None

    def _set_album_from_folder(self):
        album = self.metadata['album']
        folder = self.file_path.parent.name
        if album and album != '':
            if self.interactive:
                answer = self._set_album(album, folder)
                if answer == 'c':
                    self.metadata['album'] = input('album=')
                if answer == 'a':
                    self.metadata['album'] = album
                elif answer == 'f':
                    self.metadata['album'] = folder

        if not album or album == '':
            self.metadata['album'] = folder

    def get_metadata(self, root, loc=None, db=None, cache=False) -> dict:
        """
        Get a dictionary of metadata from exif.
        All keys will be present and have a value of None if not obtained.
        """
        self.metadata = {}
        self.metadata['checksum'] = utils.checksum(self.file_path)

        db_checksum = False
        location_id = None
        if cache and db:
            relpath, db_checksum = self._check_file(db, root)
        if db_checksum:
            location_id = self._set_metadata_from_db(db, relpath)
        else:
            self._set_metadata_from_exif()

        self.metadata['date_media'] = self.get_date_media()

        self._set_location_metadata(location_id, db, loc)

        if self.album_from_folder:
            self._set_album_from_folder()

        return self.metadata

    def has_exif_data(self):
        """Check if file has metadata, date original"""
        if not self.metadata:
            return False

        if 'date_original' in self.metadata:
            if self.metadata['date_original']:
                return True

        return False

    def set_value(self, tag, value):
        """Set value of a tag.

        :returns: value (str)
        """
        return ExifTool(self.file_path, logger=self.logger).setvalue(tag, value)

    def set_key_values(self, key, value):
        """Set tags values for given key"""
        status = True
        if self.exif_metadata is None:
            return False

        for tag in self.tags_keys[key]:
            if tag in self.exif_metadata:
                if not self.set_value(tag, value):
                    status = False

        return status

    def set_date_media(self, time):
        """Set the date/time a photo was taken.

        :param datetime time: datetime object of when the photo was taken
        :returns: bool
        """
        if time is None:
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

        if self.metadata['longitude_ref']:
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
        return self.set_value('album', self.file_path.parent.name)


class Medias:
    """Get media data in collection or source path"""

    def __init__(
        self,
        paths,
        root,
        album_from_folder=False,
        cache=False,
        db=None,
        interactive=False,
        ignore_tags=None,
        logger=logging.getLogger(),
        use_date_filename=False,
        use_file_dates=False,
    ):

        # Modules
        self.db = db
        self.paths = paths

        # Arguments
        self.root = root

        # Options
        self.cache = cache
        self.album_from_folder = album_from_folder
        self.ignore_tags = ignore_tags
        self.interactive = interactive
        self.logger = logger.getChild(self.__class__.__name__)
        self.use_date_filename = use_date_filename
        self.use_file_dates = use_file_dates

        # Attributes
        # List to store medias datas
        self.datas = {}
        self.theme = request.load_theme()

    def get_media(self, file_path, src_dir, loc=None):
        media = Media(
            file_path,
            src_dir,
            self.album_from_folder,
            self.ignore_tags,
            self.interactive,
            self.logger,
            self.use_date_filename,
            self.use_file_dates,
        )
        media.get_metadata(self.root, loc, self.db.sqlite, self.cache)

        return media

    def get_medias(self, src_dirs, imp=False, loc=None):
        """Get medias data"""
        for src_dir in src_dirs:
            src_dir = self.paths.check(src_dir)
            paths = self.paths.get_paths_list(src_dir)

            # Get medias and src_dirs
            for src_path in paths:
                if self.root not in src_path.parents:
                    if not imp:
                        self.logger.error(f"""{src_path} not in {self.root}
                                collection, use `ordigi import`""")
                        sys.exit(1)

                # Get file metadata
                media = self.get_media(src_path, src_dir, loc)

                yield media

    def update_exif_data(self, metadata):

        file_path = self.root / metadata['file_path']
        exif = WriteExif(file_path, metadata, self.ignore_tags)

        updated = False
        if self.album_from_folder:
            exif.set_album_from_folder()
            updated = True
        if metadata['original_name'] in (False, ''):
            exif.set_value('original_name', metadata['filename'])
            updated = True
        if self.album_from_folder:
            album = metadata['album']
            if album and album != '':
                exif.set_value('album', album)
                updated = True

        if updated:
            return True

        return False


