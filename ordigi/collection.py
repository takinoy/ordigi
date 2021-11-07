"""
Collection methods.
"""
from copy import copy
from datetime import datetime, timedelta
import filecmp
from fnmatch import fnmatch
import os
import re
import shutil
import sys
import logging
from pathlib import Path, PurePath

import inquirer

from ordigi.database import Sqlite
from ordigi.media import Media
from ordigi.images import Image, Images
from ordigi import request
from ordigi.summary import Summary
from ordigi import utils


class FPath:
    """Featured path object"""

    def __init__(self, path_format, day_begins=0, logger=logging.getLogger()):
        self.day_begins = day_begins
        self.items = self.get_items()
        self.logger = logger
        self.path_format = path_format
        self.whitespace_regex = '[ \t\n\r\f\v]+'
        self.whitespace_sub = '_'

    def get_items(self):
        return {
            'album': '{album}',
            'stem': '{stem}',
            'camera_make': '{camera_make}',
            'camera_model': '{camera_model}',
            'city': '{city}',
            'custom': '{".*"}',
            'country': '{country}',
            'date': '{(%[a-zA-Z][^a-zA-Z]*){1,8}}',  # search for date format string
            'ext': '{ext}',
            'folder': '{folder}',
            'folders': r'{folders(\[[0-9:]{0,3}\])?}',
            'location': '{location}',
            'name': '{name}',
            'original_name': '{original_name}',
            'state': '{state}',
            'title': '{title}',
        }

    def get_early_morning_photos_date(self, date, mask):
        """check for early hour photos to be grouped with previous day"""

        for m in '%H', '%M', '%S','%I', '%p', '%f':
            if m in mask:
                # D'ont change date format if datestring contain hour, minutes or seconds...
                return date.strftime(mask)

        if date.hour < self.day_begins:
            self.logger.info(
                "moving this photo to the previous day for classification purposes"
            )

            # push it to the day before for classification purposes
            date = date - timedelta(hours=date.hour + 1)

        return date.strftime(mask)

    def _get_folders(self, folders, mask):
        """
        Get folders part
        :params: Part, list
        :returns: list
        """
        n = len(folders) - 1

        if not re.search(r':', mask):
            a = re.compile(r'[0-9]')
            match = re.search(a, mask)
            if match:
                # single folder example: folders[1]
                i = int(match[0])
                if i > n:
                    # i is out of range, use ''
                    return ['']
                else:
                    return folders[i]
            else:
                # all folders example: folders
                return folders
        else:
            # multiple folder selection: example folders[1:3]
            a = re.compile(r'[0-9]:')
            b = re.compile(r':[0-9]')
            begin = int(re.search(a, mask)[0][0])
            end = int(re.search(b, mask)[0][1])

            if begin > n:
                # no matched folders
                return ['']
            if end > n:
                end = n

            if begin >= end:
                return ['']
            else:
                # select matched folders
                return folders[begin:end]

    def get_part(self, item, mask, metadata):
        """Parse a specific folder's name given a mask and metadata.

        :param item: Name of the item as defined in the path (i.e. date from %date)
        :param mask: Mask representing the template for the path (i.e. %city %state
        :param metadata: Metadata dictionary.
        :returns: str
        """

        # Each item has its own custom logic and we evaluate a single item and return
        # the evaluated string.
        part = ''
        filename = metadata['filename']
        stem = os.path.splitext(filename)[0]
        if item == 'stem':
            part = stem
        elif item == 'ext':
            part = os.path.splitext(filename)[1][1:]
        elif item == 'name':
            # Remove date prefix added to the name.
            part = stem
            for i, rx in utils.get_date_regex(stem):
                part = re.sub(rx, '', part)
        elif item == 'date':
            date = metadata['date_media']
            # early morning photos can be grouped with previous day
            if date is not None:
                part = self.get_early_morning_photos_date(date, mask)
        elif item == 'folder':
            folder = os.path.basename(metadata['subdirs'])
            if folder != metadata['src_dir']:
                part = folder
        elif item == 'folders':
            folders = Path(metadata['subdirs']).parts
            folders = self._get_folders(folders, mask)
            part = os.path.join(*folders)

        elif item in (
            'album',
            'camera_make',
            'camera_model',
            'city',
            'country',
            'location',
            'original_name',
            'state',
            'title',
        ):
            if item == 'location':
                mask = 'default'

            if metadata[mask]:
                part = metadata[mask]
        elif item in 'custom':
            # Fallback string
            part = mask[1:-1]

        return part

    def _set_case(self, regex, part, this_part):
        # Capitalization
        u_regex = '%u' + regex
        l_regex = '%l' + regex
        if re.search(u_regex, this_part):
            return re.sub(u_regex, part.upper(), this_part)
        if re.search(l_regex, this_part):
            return re.sub(l_regex, part.lower(), this_part)

        return re.sub(regex, part, this_part)

    def get_path_part(self, this_part, metadata):
        """Build path part
        :returns: part (string)"""
        for item, regex in self.items.items():
            matched = re.search(regex, this_part)
            if matched:
                part = self.get_part(item, matched.group()[1:-1], metadata)

                part = part.strip()

                if part == '':
                    # delete separator if any
                    regex = '[-_ .]?(%[ul])?' + regex
                    this_part = re.sub(regex, part, this_part)
                else:
                    if self.whitespace_sub != ' ':
                        # Lastly we want to sanitize the name
                        path_string = re.sub(
                            self.whitespace_regex, self.whitespace_sub, this_part
                        )
                    this_part = self._set_case(regex, part, this_part)

        # Delete separator char at the begining of the string if any:
        if this_part:
            regex = '[-_ .]'
            if re.match(regex, this_part[0]):
                this_part = this_part[1:]

        return this_part

    def get_path(self, metadata: dict) -> list:
        """
        path_format: {%Y-%d-%m}/%u{city}/{album}
        Returns file path.
        """
        path_format = self.path_format
        path = []
        path_parts = path_format.split('/')
        for path_part in path_parts:
            this_parts = path_part.split('|')
            for this_part in this_parts:
                part = self.get_path_part(this_part, metadata)

                if part != '':
                    # Check if all masks are substituted
                    if True in [c in part for c in '{}']:
                        self.logger.error(
                            f'Format path part invalid: \
                                {this_part}'
                        )
                        sys.exit(1)

                    path.append(part)
                    # We break as soon as we have a value to append
                    break
                # Else we continue for fallbacks

        # If last path is empty or start with dot
        if part == '' or re.match(r'^\..*', part):
            path.append(metadata['filename'])

        return os.path.join(*path)


class CollectionDb:

    def __init__(self, root):
        self.sqlite = Sqlite(root)

    def _format_row_data(self, table, metadata):
        row_data = {}
        for title in self.sqlite.tables[table]['header']:
            key = utils.camel2snake(title)
            row_data[title] = metadata[key]

        return row_data

    def add_file_data(self, metadata):
        """Save metadata informations to db"""
        loc_values = self._format_row_data('location', metadata)
        metadata['location_id'] = self.sqlite.add_row('location', loc_values)

        row_data = self._format_row_data('metadata', metadata)
        self.sqlite.add_row('metadata', row_data)


class FileIO:
    """File Input/Ouput operations for collection"""
    def __init__(self, dry_run=False, logger=logging.getLogger()):
        # Options
        self.dry_run = dry_run
        self.logger = logger.getChild(self.__class__.__name__)

    def copy(self, src_path, dest_path):
        if not self.dry_run:
            shutil.copy2(src_path, dest_path)
        self.logger.info(f'copy: {src_path} -> {dest_path}')

    def move(self, src_path, dest_path):
        if not self.dry_run:
            # Move the file into the destination directory
            shutil.move(src_path, dest_path)

        self.logger.info(f'move: {src_path} -> {dest_path}')

    def remove(self, path):
        if not self.dry_run:
            os.remove(path)

        self.logger.info(f'remove: {path}')

    def rmdir(self, directory):
        if not self.dry_run:
            directory.rmdir()

        self.logger.info(f'remove dir: {directory}')


class Paths:
    """Get filtered files paths"""

    def __init__(
        self,
        exclude=None,
        extensions=None,
        glob='**/*',
        interactive=False,
        logger=logging.getLogger(),
        max_deep=None,
    ):

        # Options
        self.exclude = exclude

        if extensions and '%media' in extensions:
            extensions.remove('%media')
            self.extensions = extensions.union(Media.extensions)
        else:
            self.extensions = extensions

        self.glob = glob
        self.interactive = interactive
        self.logger = logger.getChild(self.__class__.__name__)
        self.max_deep = max_deep
        self.paths_list = []

        # Arguments
        self.theme = request.load_theme()

    def check(self, path):
        """
        :param: str path
        :return: Path path
        """
        # some error checking
        if not path.exists():
            self.logger.error(f'Directory {path} does not exist')
            sys.exit(1)

        return path

    def get_images(self, path):
        """
        :returns: iter
        """
        for src_path in self.get_files(path):
            dirname = src_path.parent.name

            if dirname.find('similar_to') == 0:
                continue

            image = Image(src_path)

            if image.is_image():
                yield image

    def get_files(self, path):
        """Recursively get files which match a path and extension.

        :param str path string: Path to start recursive file listing
        :returns: Path file_path, Path subdirs
        """
        for path0 in path.glob(self.glob):
            if path0.is_dir():
                continue

            file_path = path0
            subdirs = file_path.relative_to(path).parent
            if self.glob == '*':
                level = 0
            else:
                level = len(subdirs.parts)

            if path / '.ordigi' in file_path.parents:
                continue

            if self.max_deep is not None:
                if level > self.max_deep:
                    continue

            if self.exclude:
                matched = False
                for exclude in self.exclude:
                    if fnmatch(file_path, exclude):
                        matched = True
                        break
                if matched:
                    continue

            if (
                not self.extensions
                or PurePath(file_path).suffix.lower()[1:] in self.extensions
            ):
                # return file_path and subdir
                yield file_path

    def walklevel(self, src_dir, maxlevel=None):
        """
        Walk into input directory recursively until desired maxlevel
        source: https://stackoverflow.com/questions/229186/os-walk-without-digging-into-directories-below
        """
        src_dir = str(src_dir)
        if not os.path.isdir(src_dir):
            return None

        num_sep = src_dir.count(os.path.sep)
        for root, dirs, files in os.walk(src_dir):
            level = root.count(os.path.sep) - num_sep
            yield root, dirs, files, level
            if maxlevel is not None and level >= maxlevel:
                del dirs[:]

    def _modify_selection(self):
        """
        :params: list
        :return: list
        """
        message = "Bellow the file selection list, modify selection if needed"
        questions = [
            inquirer.Checkbox(
                'selection',
                message=message,
                choices=self.paths_list,
                default=self.paths_list,
            ),
        ]
        return inquirer.prompt(questions, theme=self.theme)['selection']

    def get_paths_list(self, path):
        self.paths_list = list(self.get_files(path))
        if self.interactive:
            self.paths_list = self._modify_selection()
            print('Processing...')

        return self.paths_list


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

        # Attributes
        self.root = root

        # Options
        self.cache = cache
        self.album_from_folder = album_from_folder
        self.ignore_tags = ignore_tags
        self.interactive = interactive
        self.logger = logger.getChild(self.__class__.__name__)
        self.use_date_filename = use_date_filename
        self.use_file_dates = use_file_dates

        # List to store media metadata
        self.medias = []

        # Arguments
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

    def update_exif_data(self, media):
        updated = False
        if self.album_from_folder:
            media.set_album_from_folder()
            updated = True
        if media.metadata['original_name'] in (False, ''):
            media.set_value('original_name', media.metadata['filename'])
            updated = True
        if self.album_from_folder:
            album = media.metadata['album']
            if album and album != '':
                media.set_value('album', album)
                updated = True

        if updated:
            return True

        return False


class SortMedias:
    """Sort medias in collection"""

    def __init__(
        self,
        fileio,
        medias,
        root,
        db=None,
        dry_run=False,
        interactive=False,
        logger=logging.getLogger(),
    ):

        # Attributes
        self.fileio = fileio
        self.medias = medias
        self.root = root

        # Options
        self.db = db
        self.dry_run = dry_run
        self.interactive = interactive
        self.logger = logger.getChild(self.__class__.__name__)
        self.summary = Summary(self.root)

        # Arguments
        self.theme = request.load_theme()

    def _checkcomp(self, dest_path, src_checksum):
        """Check file."""
        if self.dry_run:
            return True

        dest_checksum = utils.checksum(dest_path)

        if dest_checksum != src_checksum:
            self.logger.info(
                f'Source checksum and destination checksum are not the same'
            )
            return False

        return True

    def _record_file(self, src_path, dest_path, media, imp=False):
        """Check file and record the file to db"""
        # Check if file remain the same
        checksum = media.metadata['checksum']
        if not self._checkcomp(dest_path, checksum):
            self.logger.error(f'Files {src_path} and {dest_path} are not identical')
            self.summary.append('check', False, src_path, dest_path)
            return False

        # TODO put this to Medias class???
        # change media file_path to dest_path
        media.file_path = dest_path
        if not self.dry_run:
            updated = self.medias.update_exif_data(media)
            if updated:
                checksum = utils.checksum(dest_path)
                media.metadata['checksum'] = checksum

        if not self.dry_run:
            self.db.add_file_data(media.metadata)
            if imp != 'copy' and self.root in src_path.parents:
                self.db.sqlite.delete_filepath(str(src_path.relative_to(self.root)))

        return True

    def _set_summary(self, result, src_path, dest_path, imp=False):
        if result:
            if imp:
                self.summary.append('import', True, src_path, dest_path)
            else:
                self.summary.append('sort', True, src_path, dest_path)
        else:
            if imp:
                self.summary.append('import', False, src_path, dest_path)
            else:
                self.summary.append('sort', False, src_path, dest_path)


    def sort_file(self, src_path, dest_path, media, imp=False):
        """Sort file and register it to db"""
        if imp == 'copy':
            self.fileio.copy(src_path, dest_path)
        else:
            self.fileio.move(src_path, dest_path)

        if self.db:
            result = self._record_file(
                src_path, dest_path, media, imp=imp
            )
        else:
            result = True

        self._set_summary(result, src_path, dest_path, imp)

        return self.summary

    def _create_directories(self, medias):
        """Create a directory if it does not already exist.

        :param Path: A fully qualified path of the to create.
        :returns: bool
        """
        for media in medias:
            relpath = os.path.dirname(media.metadata['file_path'])
            directory_path = self.root / relpath
            parts = directory_path.relative_to(self.root).parts
            for i, _ in enumerate(parts):
                dir_path = self.root / Path(*parts[0 : i + 1])
                if dir_path.is_file():
                    self.logger.warning(f'Target directory {dir_path} is a file')
                    # Rename the src_file
                    if self.interactive:
                        prompt = [
                            inquirer.Text(
                                'file_path',
                                message="New name for" f"'{dir_path.name}' file",
                            ),
                        ]
                        answers = inquirer.prompt(prompt, theme=self.theme)
                        file_path = dir_path.parent / answers['file_path']
                    else:
                        file_path = dir_path.parent / (dir_path.name + '_file')

                    self.logger.warning(f'Renaming {dir_path} to {file_path}')
                    if not self.dry_run:
                        shutil.move(dir_path, file_path)
                    for med in medias:
                        if med.file_path == dir_path:
                            med.file_path = file_path
                            break

            if not self.dry_run:
                directory_path.mkdir(parents=True, exist_ok=True)
            self.logger.info(f'Create {directory_path}')

    def check_conflicts(self, src_path, dest_path, remove_duplicates=False):
        '''
        Check if file can be copied or moved file to dest_path.
        Return True if success, None is no filesystem action, False if
        conflicts.
        :params: str, str, bool
        :returns: bool or None
        '''

        # check for collisions
        if src_path == dest_path:
            self.logger.info(f"File {dest_path} already sorted")
            return 2
        if dest_path.is_dir():
            self.logger.info(f"File {dest_path} is a existing directory")
            return 1
        elif dest_path.is_file():
            self.logger.info(f"File {dest_path} already exist")
            if remove_duplicates:
                if filecmp.cmp(src_path, dest_path):
                    self.logger.info(
                        f"File in source and destination are identical. Duplicate will be ignored."
                    )
                    return 3
                else:  # name is same, but file is different
                    self.logger.info(
                        f"File {src_path} and {dest_path} are different."
                    )
                    return 1
            else:
                return 1
        else:
            return 0

    def _solve_conflicts(self, conflicts, remove_duplicates):
        result = False
        unresolved_conflicts = []
        while conflicts != []:
            src_path, dest_path, media = conflicts.pop()
            # Check for conflict status again in case is has changed
            conflict = self.check_conflicts(src_path, dest_path, remove_duplicates)
            n = 1
            while conflict == 1 and n < 100:
                # Add appendix to the name
                suffix = dest_path.suffix
                if n > 1:
                    stem = dest_path.stem.rsplit('_' + str(n - 1))[0]
                else:
                    stem = dest_path.stem
                dest_path = dest_path.parent / (stem + '_' + str(n) + suffix)
                conflict = self.check_conflicts(src_path, dest_path, remove_duplicates)
                n = n + 1

            if conflict == 1:
                # n > 100:
                unresolved_conflicts.append((src_path, dest_path, media))
                self.logger.error(f"Too many appends for {dest_path}")

            media.metadata['file_path'] = os.path.relpath(dest_path, self.root)

            yield (src_path, dest_path, media), conflict

    def sort_medias(self, medias, imp=False, remove_duplicates=False):
        """
        sort files and solve conflicts
        """
        # Create directories
        self._create_directories(medias)

        conflicts = []
        for media in medias:
            src_path = media.file_path
            dest_path = self.root / media.metadata['file_path']

            conflict = self.check_conflicts(src_path, dest_path, remove_duplicates)

            if not conflict:
                self.sort_file(
                    src_path, dest_path, media, imp=imp
                    )
            elif conflict == 1:
                # There is conflict and file are different
                conflicts.append((src_path, dest_path, media))
            elif conflict == 3:
                # Same file checksum
                if imp == 'move':
                    self.fileio.remove(src_path)
            elif conflict == 2:
                # File already sorted
                pass

        if conflicts != []:
            for files_data, conflict in self._solve_conflicts(conflicts,
                remove_duplicates):

                src_path, dest_path, media = files_data
                if not conflict:
                    self.sort_file(
                        src_path, dest_path, media, imp=imp
                        )
                elif conflict == 1:
                    # There is unresolved conflict
                    self._set_summary(False, src_path, dest_path, imp)
                elif conflict == 3:
                    # Same file checksum
                    if imp == 'move':
                        self.fileio.remove(src_path)
                elif conflict == 2:
                    # File already sorted
                    pass

        return self.summary


class Collection(SortMedias):
    """Class of the media collection."""
    def __init__(
        self,
        root,
        album_from_folder=False,
        cache=False,
        day_begins=0,
        dry_run=False,
        exclude=None,
        extensions=None,
        glob='**/*',
        interactive=False,
        ignore_tags=None,
        logger=logging.getLogger(),
        max_deep=None,
        use_date_filename=False,
        use_file_dates=False,
    ):

        # Modules
        self.db = CollectionDb(root)
        self.fileio = FileIO(dry_run, logger)
        self.paths = Paths(
            exclude,
            extensions,
            glob,
            interactive,
            logger,
            max_deep,
        )

        self.medias = Medias(
            self.paths,
            root,
            album_from_folder,
            cache,
            self.db,
            interactive,
            ignore_tags,
            logger,
            use_date_filename,
            use_file_dates,
        )

        # Features
        super().__init__(
            self.fileio,
            self.medias,
            root,
            self.db,
            dry_run,
            interactive,
            logger,
        )

        # Attributes
        if not self.root.exists():
            logger.error(f'Directory {self.root} does not exist')
            sys.exit(1)

        # Options
        self.day_begins = day_begins
        self.glob = glob
        self.logger = logger.getChild(self.__class__.__name__)

        self.summary = Summary(self.root)

        # Arguments
        self.theme = request.load_theme()

    def get_collection_files(self, exclude=True):
        if exclude:
            exclude = self.paths.exclude

        paths = Paths(
            exclude,
            interactive=self.interactive,
            logger=self.logger,
        )
        for file_path in paths.get_files(self.root):
            yield file_path

    def init(self, loc):
        for file_path in self.get_collection_files():
            media = self.medias.get_media(file_path, self.root, loc)
            media.metadata['file_path'] = os.path.relpath(file_path, self.root)

            self.db.add_file_data(media.metadata)
            self.summary.append('update', file_path)

        return self.summary

    def check_db(self):
        """
        Check if db FilePath match to collection filesystem
        :returns: bool
        """
        file_paths = list(self.get_collection_files())
        db_rows = [row['FilePath'] for row in self.db.sqlite.get_rows('metadata')]
        for file_path in file_paths:
            relpath = os.path.relpath(file_path, self.root)
            # If file not in database
            if relpath not in db_rows:
                self.logger.error('Db data is not accurate')
                self.logger.info(f'{file_path} not in db')
                return False

        nb_files = len(file_paths)
        nb_row = len(db_rows)
        if nb_row != nb_files:
            self.logger.error('Db data is not accurate')
            return False

        return True

    def _init_check_db(self, loc=None):
        if self.db.sqlite.is_empty('metadata'):
            self.init(loc)
        elif not self.check_db():
            self.logger.error('Db data is not accurate run `ordigi update`')
            sys.exit(1)

    def update(self, loc):
        file_paths = list(self.get_collection_files())
        db_rows = list(self.db.sqlite.get_rows('metadata'))
        invalid_db_rows = set()
        db_paths = set()
        for db_row in db_rows:
            abspath = self.root / db_row['FilePath']
            if abspath not in file_paths:
                invalid_db_rows.add(db_row)

            db_paths.add(db_row['FilePath'])

        for file_path in file_paths:
            relpath = os.path.relpath(file_path, self.root)
            # If file not in database
            if relpath not in db_paths:
                media = self.medias.get_media(file_path, self.root, loc)
                media.metadata['file_path'] = relpath
                # Check if file checksum is in invalid rows
                row = []
                for row in invalid_db_rows:
                    if row['Checksum'] == media.metadata['checksum']:
                        # file have been moved without registering to db
                        media.metadata['src_path'] = row['SrcPath']
                        # Check if row FilePath is a subpath of relpath
                        if relpath.startswith(row['FilePath']):
                            d = os.path.relpath(relpath, row['FilePath'])
                            media.metadata['subdirs'] = row['Subdirs'] + d
                        media.metadata['Filename'] = row['Filename']
                        break
                # set row attribute to the file
                self.db.add_file_data(media.metadata)
                self.summary.append('update', file_path)

        # Finally delete invalid rows
        for row in invalid_db_rows:
            self.db.sqlite.delete_filepath(row['FilePath'])

        return self.summary

    def check_files(self):
        for file_path in self.paths.get_files(self.root):
            checksum = utils.checksum(file_path)
            relpath = file_path.relative_to(self.root)
            if checksum == self.db.sqlite.get_checksum(relpath):
                self.summary.append('check',True, file_path)
            else:
                self.logger.error('{file_path} is corrupted')
                self.summary.append('check', False, file_path)

        return self.summary

    def set_utime_from_metadata(self, date_media, file_path):
        """Set the modification time on the file based on the file name."""

        # Initialize date taken to what's returned from the metadata function.
        os.utime(
            file_path, (int(datetime.now().timestamp()), int(date_media.timestamp()))
        )

    def remove_excluded_files(self):
        """Remove excluded files in collection"""
        result = True
        # get all files
        for file_path in self.get_collection_files(exclude=False):
            for exclude in self.paths.exclude:
                if fnmatch(file_path, exclude):
                    self.fileio.remove(file_path)
                    self.summary.append('remove', True, file_path)
                    break

        return self.summary

    def remove_empty_subdirs(self, directories, src_dirs):
        """Remove empty subdir after moving files"""
        parents = set()
        for directory in directories:
            self.logger.info(f'remove empty subdirs')
            if not directory.is_dir():
                continue

            if str(directory) in src_dirs:
                continue

            # if folder empty, delete it
            files = os.listdir(directory)
            if len(files) == 0:
                self.fileio.rmdir(directory)

            if self.root in directory.parent.parents:
                parents.add(directory.parent)

        if parents != set():
            self.remove_empty_subdirs(parents, src_dirs)

    def remove_empty_folders(self, directory, remove_root=True):
        """Remove empty sub-folders in collection"""
        if not os.path.isdir(directory):
            self.summary.append('remove', False, directory)
            return self.summary

        # remove empty subfolders
        files = os.listdir(directory)
        if len(files):
            for f in files:
                fullpath = os.path.join(directory, f)
                if os.path.isdir(fullpath):
                    self.remove_empty_folders(fullpath)

        # if folder empty, delete it
        files = os.listdir(directory)
        if len(files) == 0 and remove_root:
            self.logger.info(f"Removing empty folder: {directory}")
            if not self.dry_run:
                os.rmdir(directory)
            self.summary.append('remove', True, directory)

        return self.summary

    def sort_files(
            self, src_dirs, path_format, loc,
            imp=False, remove_duplicates=False
        ):
        """
        Sort files into appropriate folder
        """
        # Check db
        self._init_check_db(loc)

        # Get medias data
        medias = []
        subdirs = set()
        for media in self.medias.get_medias(src_dirs, imp=imp, loc=loc):
            # Get the destination path according to metadata
            fpath = FPath(path_format, self.day_begins, self.logger)
            media.metadata['file_path'] = fpath.get_path(media.metadata)
            subdirs.add(media.file_path.parent)

            medias.append(copy(media))

        # Sort files and solve conflicts
        self.summary = self.sort_medias(medias, imp, remove_duplicates)

        if imp != 'copy':
            self.remove_empty_subdirs(subdirs, src_dirs)

        if not self.check_db():
            self.summary.append('check', False)

        return self.summary

    def dedup_regex(self, paths, dedup_regex=None, remove_duplicates=False):
        """Deduplicate file path parts"""

        # Check db
        self._init_check_db()

        # Delimiter regex
        delim = r'[-_ .]'
        # Numeric date item  regex
        d = r'\d{2}'

        # Numeric date regex
        if not dedup_regex:
            date_num2 = re.compile(
                fr'([^0-9]{d}{delim}{d}{delim}|{delim}{d}{delim}{d}[^0-9])'
            )
            date_num3 = re.compile(
                fr'([^0-9]{d}{delim}{d}{delim}{d}{delim}|{delim}{d}{delim}{d}{delim}{d}[^0-9])'
            )
            default = re.compile(r'([^-_ .]+[-_ .])')
            dedup_regex = [date_num3, date_num2, default]

        # Get medias data
        medias = []
        for media in self.medias.get_medias(paths):
            # Deduplicate the path
            src_path = media.file_path
            path_parts = src_path.relative_to(self.root).parts
            dedup_path = []
            for path_part in path_parts:
                items = utils.split_part(dedup_regex.copy(), path_part)

                filtered_items = []
                for item in items:
                    if item not in filtered_items:
                        filtered_items.append(item)

                dedup_path.append(''.join(filtered_items))

            media.metadata['file_path'] = os.path.join(*dedup_path)
            medias.append(copy(media))

        # Sort files and solve conflicts
        self.sort_medias(medias, remove_duplicates=remove_duplicates)

        if not self.check_db():
            self.summary.append('check', False)

        return self.summary

    def _find_similar_images(self, image, images, path, dest_dir, similarity=80):
        medias = []
        if not image.img_path.is_file():
            return medias

        name = image.img_path.stem
        directory_name = os.path.join(dest_dir, name.replace('.', '_'))

        for img_path in images.find_similar(image, similarity):
            self.paths.paths_list.append(img_path)

            media = self.medias.get_media(img_path, path)
            relpath = os.path.join(directory_name, image.img_path.name)
            media.metadata['file_path'] = relpath
            medias.append(copy(media))

        if medias:
            # Found similar images to image
            self.paths.paths_list.append(image.img_path)
            media = self.medias.get_media(image.img_path, path)
            relpath = os.path.join(directory_name, image.img_path.name)
            media.metadata['file_path'] = relpath
            medias.insert(0, copy(media))

        return medias

    def sort_similar_images(self, path, similarity=80, remove_duplicates=False):
        """Sort similar images using imagehash library"""
        # Check db
        self._init_check_db()

        dest_dir = 'similar_images'
        path = self.paths.check(path)

        images_paths = set(self.paths.get_images(path))
        images = Images(images_paths, logger=self.logger)
        nb_row_ini = self.db.sqlite.len('metadata')
        for image in images_paths:
            medias = self._find_similar_images(
                image, images, path, dest_dir, similarity
            )
            if medias:
                # Move the simlars file into the destination directory
                self.sort_medias(medias, remove_duplicates=remove_duplicates)

        nb_row_end = self.db.sqlite.len('metadata')
        if nb_row_ini and nb_row_ini != nb_row_end:
            self.logger.error('Nb of row have changed unexpectedly')

        if not self.check_db():
            self.summary.append('check', False)

        return self.summary

    def fill_metadata(self, path, key, loc=None, overwrite=False):
        """Fill metadata and exif data for given key"""
        self._init_check_db()

        if key in (
                'latitude',
                'longitude',
                'latitude_ref',
                'longitude_ref',
                ):
            print(f"Set {key} alone is not allowed")
            return None

        if overwrite:
            print(f"Edit {key} values:")
        else:
            print(f"Fill empty {key} values:")

        paths = self.paths.get_paths_list(path)

        for file_path in paths:
            media = self.medias.get_media(file_path, self.root, loc)
            print()
            value = media.metadata[key]
            if overwrite or not value:
                print(f"FILE: '{file_path}'")
            if overwrite:
                print(f"{key}: '{value}'")
            if overwrite or not value:
                # Prompt value for given key for file_path
                # utils.open_file()
                prompt = [
                    inquirer.Text('value', message=key),
                ]
                answer = inquirer.prompt(prompt, theme=self.theme)
                # Validate value
                if key in ('date_original', 'date_created', 'date_modified'):
                    # Check date format
                    value = str(media.get_date_format(answer['value']))
                else:
                    if not answer[key].isalnum():
                        print("Invalid entry, use alphanumeric chars")
                        value = inquirer.prompt(prompt, theme=self.theme)

                # print(f"{key}='{value}'")

                media.metadata[key] = value
                # Update database
                self.db.add_file_data(media.metadata)
                # Update exif data
                media.set_key_values(key, value)

                self.summary.append('update', False, file_path)

        return self.summary
