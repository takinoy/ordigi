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
                    this_part = self._set_case(regex, part, this_part)

        # Delete separator char at the begining of the string if any:
        if this_part:
            regex = '[-_ .]'
            if re.match(regex, this_part[0]):
                this_part = this_part[1:]

        return this_part.strip()

    def get_path(self, metadata, whitespace_sub='_'):
        """path_format: {%Y-%d-%m}/%u{city}/{album}

        Returns file path.

        :returns: string"""

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

        path_string = os.path.join(*path)

        if whitespace_sub != ' ':
            # Lastly we want to sanitize the name
            path_string = re.sub(self.whitespace_regex, whitespace_sub, path_string)

        return path_string

        return None


class Collection:
    """Class of the media collection."""

    def __init__(
        self,
        root,
        album_from_folder=False,
        cache=False,
        day_begins=0,
        dry_run=False,
        exclude=set(),
        filter_by_ext=set(),
        glob='**/*',
        interactive=False,
        logger=logging.getLogger(),
        max_deep=None,
        use_date_filename=False,
        use_file_dates=False,
    ):

        # Attributes
        self.root = root.expanduser().absolute()
        if not self.root.exists():
            logger.error(f'Directory {self.root} does not exist')
            sys.exit(1)

        self.db = Sqlite(self.root)

        # Options
        self.album_from_folder = album_from_folder
        self.cache = cache
        self.day_begins = day_begins
        self.dry_run = dry_run
        self.exclude = exclude

        if '%media' in filter_by_ext:
            filter_by_ext.remove('%media')
            self.filter_by_ext = filter_by_ext.union(Media.extensions)
        else:
            self.filter_by_ext = filter_by_ext

        self.glob = glob
        self.interactive = interactive
        self.logger = logger.getChild(self.__class__.__name__)
        self.max_deep = max_deep
        # List to store media metadata
        self.medias = []
        self.summary = Summary(self.root)
        self.use_date_filename = use_date_filename
        self.use_file_dates = use_file_dates

        self.src_list = []
        self.dest_list = []

        # Constants
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

    def _format_row_data(self, table, metadata):
        row_data = {}
        for title in self.db.tables[table]['header']:
            key = utils.camel2snake(title)
            row_data[title] = metadata[key]

        return row_data

    def _add_db_data(self, metadata):
        loc_values = self._format_row_data('location', metadata)
        metadata['location_id'] = self.db.add_row('location', loc_values)

        row_data = self._format_row_data('metadata', metadata)
        self.db.add_row('metadata', row_data)

    def _update_exif_data(self, media):
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

    def remove(self, file_path):
        if not self.dry_run:
            os.remove(file_path)
        self.logger.info(f'remove: {file_path}')

    def remove_excluded_files(self):
        result = True
        for file_path in self.root.glob(self.glob):
            if file_path.is_dir():
                continue
            else:
                if self.root / '.ordigi' in file_path.parents:
                    continue

                for exclude in self.exclude:
                    if fnmatch(file_path, exclude):
                        if not self.dry_run:
                            self.remove(file_path)
                        self.summary.append('remove', True, file_path)
                        break

        return self.summary

    def _check_file(self, src_path, dest_path, media):
        checksum = media.metadata['checksum']
        if not self._checkcomp(dest_path, checksum):
            self.logger.error(f'Files {src_path} and {dest_path} are not identical')
            self.summary.append('check', False, src_path, dest_path)
            return False

        # change media file_path to dest_path
        media.file_path = dest_path
        if not self.dry_run:
            updated = self._update_exif_data(media)
            if updated:
                checksum = utils.checksum(dest_path)
                media.metadata['checksum'] = checksum

        media.metadata['file_path'] = os.path.relpath(dest_path, self.root)

        return True

    def _copy(self, src_path, dest_path):
        if not self.dry_run:
            shutil.copy2(src_path, dest_path)
        self.logger.info(f'copy: {src_path} -> {dest_path}')

    def _move(self, src_path, dest_path):
        if not self.dry_run:
            # Move the file into the destination directory
            shutil.move(src_path, dest_path)

        self.logger.info(f'move: {src_path} -> {dest_path}')

    def _remove(self, path):
        if not self.dry_run:
            self.remove(path)

        self.logger.info(f'remove: {path}')

    def _record_file(self, src_path, dest_path, media, import_mode=False):
        """Check file and record the file to db"""
        # Check if file remain the same
        if not self._check_file(src_path, dest_path, media):
            self.summary.append('check', False, src_path, dest_path)
            return False

        if not self.dry_run:
            self._add_db_data(media.metadata)
            if import_mode != 'copy' and self.root in src_path.parents:
                self.db.delete_filepath(str(src_path.relative_to(self.root)))

        return True

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

            yield (src_path, dest_path, media), conflict

    def _split_part(self, dedup_regex, path_part, items):
        """Split part from regex
        :returns: parts"""
        regex = dedup_regex.pop(0)
        parts = re.split(regex, path_part)
        # Loop thought part, search matched regex part and proceed with
        # next regex for others parts
        for n, part in enumerate(parts):
            if re.match(regex, part):
                if part[0] in '-_ .':
                    if n > 0:
                        # move the separator to previous item
                        parts[n - 1] = parts[n - 1] + part[0]
                    items.append(part[1:])
                else:
                    items.append(part)
            elif dedup_regex != []:
                # Others parts
                self._split_part(dedup_regex, part, items)
            else:
                items.append(part)

        return items

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

    def level(self, path):
        """
        :param: Path
        :return: int
        """
        return len(path.parts) - 1

    def _get_files_in_path(self, path, glob='**/*', extensions=set()):
        """Recursively get files which match a path and extension.

        :param str path string: Path to start recursive file listing
        :param tuple(str) extensions: File extensions to include (whitelist)
        :returns: Path file_path, Path subdirs
        """
        for path0 in path.glob(glob):
            if path0.is_dir():
                continue
            else:
                file_path = path0
                parts = file_path.parts
                subdirs = file_path.relative_to(path).parent
                if glob == '*':
                    level = 0
                else:
                    level = len(subdirs.parts)

                if self.root / '.ordigi' in file_path.parents:
                    continue

                if self.max_deep is not None:
                    if level > self.max_deep:
                        continue

                matched = False
                for exclude in self.exclude:
                    if fnmatch(file_path, exclude):
                        matched = True
                        break
                if matched:
                    continue

                if (
                    extensions == set()
                    or PurePath(file_path).suffix.lower() in extensions
                ):
                    # return file_path and subdir
                    yield file_path

    def _create_directory(self, directory_path, media):
        """Create a directory if it does not already exist.

        :param Path: A fully qualified path of the to create.
        :returns: bool
        """
        parts = directory_path.relative_to(self.root).parts
        for i, part in enumerate(parts):
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
                shutil.move(dir_path, file_path)
                for media in medias:
                    if media.file_path == dir_path:
                        media.file_path = file_path
                        break

        if not self.dry_run:
            directory_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f'Create {directory_path}')

    def _check_path(self, path):
        """
        :param: str path
        :return: Path path
        """
        path = Path(path).expanduser().absolute()

        # some error checking
        if not path.exists():
            self.logger.error(f'Directory {path} does not exist')
            sys.exit(1)

        return path

    def set_utime_from_metadata(self, date_media, file_path):
        """Set the modification time on the file based on the file name."""

        # Initialize date taken to what's returned from the metadata function.
        os.utime(
            file_path, (int(datetime.now().timestamp()), int(date_media.timestamp()))
        )

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

    def _sort_medias(self, files_data, import_mode=None, remove_duplicates=False):
        """
        sort files and solve conflicts
        """
        # Create directories
        for media, relpath in files_data:
            dest_directory = self.root / relpath.parent
            self._create_directory(dest_directory, media)

        conflicts = []
        for media, relpath in files_data:
            src_path = media.file_path
            dest_path = self.root / relpath

            conflict = self.check_conflicts(src_path, dest_path, remove_duplicates)

            if not conflict:
                self.sort_file(
                    src_path, dest_path, media, import_mode=import_mode
                    )
            elif conflict == 1:
                # There is conflict and file are different
                conflicts.append((src_path, dest_path, media))
            elif conflict == 3:
                # Same file checksum
                if import_mode == 'move':
                    self._remove(src_path)
                self.dest_list.append(dest_path)
            elif conflict == 2:
                # File already sorted
                self.dest_list.append(dest_path)

        if conflicts != []:
            for files_data, conflict in self._solve_conflicts(conflicts,
                    remove_duplicates):
                src_path, dest_path, media = files_data

                if not conflict:
                    self.sort_file(
                        src_path, dest_path, media, import_mode=import_mode
                        )
                elif conflict == 1:
                    # There is unresolved conflict
                    if import_mode:
                        self.summary.append('import', False, src_path, dest_path)
                    else:
                        self.summary.append('sort', False, src_path, dest_path)
                elif conflict == 3:
                    # Same file checksum
                    if import_mode == 'move':
                        self._remove(src_path)
                    self.dest_list.append(dest_path)
                elif conflict == 2:
                    # File already sorted
                    self.dest_list.append(dest_path)

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
                choices=self.src_list,
                default=self.src_list,
            ),
        ]
        return inquirer.prompt(questions, theme=self.theme)['selection']

    def _get_all_files(self):
        return [x for x in self._get_files_in_path(self.root)]

    def check_db(self):
        """
        Check if db FilePath match to collection filesystem
        :returns: bool
        """
        file_paths = [x for x in self._get_all_files()]
        db_rows = [row['FilePath'] for row in self.db.get_rows('metadata')]
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

    def _check_processed(self):
        # Finally check if are files are successfully processed
        n_fail = len(self.src_list) - len(self.dest_list)
        if n_fail != 0:
            self.logger.error(f"{n_fail} files have not be processed")
            return False

        return self.check_db()

    def _get_medias_data(
        self, src_dirs, import_mode=None, ignore_tags=set(), loc=None
    ):
        """Get medias data"""
        for src_dir in src_dirs:
            self.dest_list = []
            src_dir = self._check_path(src_dir)
            self.src_list = self._get_path_list(src_dir)

            # Get medias and src_dirs
            for src_path in self.src_list:
                if self.root not in src_path.parents:
                    if not import_mode:
                        self.logger.error(f"""{src_path} not in {self.root}
                                collection, use `ordigi import`""")
                        sys.exit(1)

                # Get file metadata
                media = Media(
                    src_path,
                    src_dir,
                    self.album_from_folder,
                    ignore_tags,
                    self.interactive,
                    self.logger,
                    self.use_date_filename,
                    self.use_file_dates,
                )
                media.get_metadata(self.root, loc, self.db, self.cache)

                yield media

    def _init_check_db(self, loc=None, ignore_tags=set()):
        if self.db.is_empty('metadata'):
            self.init(loc, ignore_tags)
        elif not self.check_db():
            self.logger.error('Db data is not accurate run `ordigi update`')
            sys.exit(1)

    def _get_path_list(self, path):
        src_list = [
            x
            for x in self._get_files_in_path(
                path, glob=self.glob,
                extensions=self.filter_by_ext,
            )
        ]
        if self.interactive:
            src_list = self._modify_selection()
            print('Processing...')

        return src_list

    def get_medias(self, loc, ignore_tags=set()):
        for file_path in self._get_all_files():
            media = Media(
                file_path,
                self.root,
                ignore_tags=ignore_tags,
                logger=self.logger,
                use_date_filename=self.use_date_filename,
                use_file_dates=self.use_file_dates,
            )
            metadata = media.get_metadata(self.root, loc, self.db, self.cache)
            media.metadata['file_path'] = os.path.relpath(file_path, self.root)
            yield media, file_path

    def init(self, loc, ignore_tags=set()):
        for media, file_path in self.get_medias(loc):
            self._add_db_data(media.metadata)
            self.summary.append('update', file_path)

        return self.summary

    def update(self, loc, ignore_tags=set()):
        file_paths = [x for x in self._get_all_files()]
        db_rows = [row for row in self.db.get_rows('metadata')]
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
                media = Media(
                    file_path,
                    self.root,
                    ignore_tags=ignore_tags,
                    logger=self.logger,
                    use_date_filename=self.use_date_filename,
                    use_file_dates=self.use_file_dates,
                )
                metadata = media.get_metadata(self.root, loc, self.db, self.cache)
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
                self._add_db_data(media.metadata)
                self.summary.append('update', file_path)

        # Finally delete invalid rows
        for row in invalid_db_rows:
            self.db.delete_filepath(row['FilePath'])

        return self.summary

    def check_files(self):
        for file_path in self._get_all_files():
            checksum = utils.checksum(file_path)
            relpath = file_path.relative_to(self.root)
            if checksum == self.db.get_checksum(relpath):
                self.summary.append('check',True, file_path)
            else:
                self.logger.error('{file_path} is corrupted')
                self.summary.append('check', False, file_path)

        return self.summary

    def _remove_empty_subdirs(self, directories, src_dirs):
        """Remove empty subdir after moving files"""
        parents = set()
        for directory in directories:
            if not directory.is_dir():
                continue

            if str(directory) in src_dirs:
                continue

            # if folder empty, delete it
            files = os.listdir(directory)
            if len(files) == 0:
                if not self.dry_run:
                    directory.rmdir()

            if self.root in directory.parent.parents:
                parents.add(directory.parent)

        if parents != set():
            self._remove_empty_subdirs(parents, src_dirs)

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

    def sort_file(self, src_path, dest_path, media, import_mode=False):
        if import_mode == 'copy':
            self._copy(src_path, dest_path)
        else:
            self._move(src_path, dest_path)

        result = self._record_file(
            src_path, dest_path, media, import_mode=import_mode
            )

        if result:
            self.dest_list.append(dest_path)
            if import_mode:
                self.summary.append('import', True, src_path, dest_path)
            else:
                self.summary.append('sort', True, src_path, dest_path)
        else:
            if import_mode:
                self.summary.append('import', False, src_path, dest_path)
            else:
                self.summary.append('sort', False, src_path, dest_path)

        return self.summary

    def sort_files(
        self, src_dirs, path_format, loc,
        import_mode=False, remove_duplicates=False, ignore_tags=set()
        ):
        """
        Sort files into appropriate folder
        """
        # Check db
        self._init_check_db(loc, ignore_tags)

        # Get medias data
        files_data = []
        subdirs = set()
        for media in self._get_medias_data(
            src_dirs,
            import_mode=import_mode, ignore_tags=ignore_tags, loc=loc,
        ):
            # Get the destination path according to metadata
            fpath = FPath(path_format, self.day_begins, self.logger)
            relpath = Path(fpath.get_path(media.metadata))
            subdirs.add(media.file_path.parent)

            files_data.append((copy(media), relpath))

        # Sort files and solve conflicts
        self._sort_medias(files_data, import_mode, remove_duplicates)

        if import_mode != 'copy':
            self._remove_empty_subdirs(subdirs, src_dirs)

        if not self._check_processed():
            self.summary.append('check', False)

        return self.summary

    def dedup_regex(self, paths, dedup_regex, remove_duplicates=False):
        """Deduplicate file path parts"""
        # Check db
        self._init_check_db()

        # Delimiter regex
        delim = r'[-_ .]'
        # Numeric date item  regex
        d = r'\d{2}'

        # Numeric date regex
        if len(dedup_regex) == 0:
            date_num2 = re.compile(
                fr'([^0-9]{d}{delim}{d}{delim}|{delim}{d}{delim}{d}[^0-9])'
            )
            date_num3 = re.compile(
                fr'([^0-9]{d}{delim}{d}{delim}{d}{delim}|{delim}{d}{delim}{d}{delim}{d}[^0-9])'
            )
            default = re.compile(r'([^-_ .]+[-_ .])')
            dedup_regex = [date_num3, date_num2, default]

        # Get medias data
        files_data = []
        for media in self._get_medias_data(paths):
            # Deduplicate the path
            src_path = media.file_path
            path_parts = src_path.relative_to(self.root).parts
            dedup_path = []
            for path_part in path_parts:
                items = []
                items = self._split_part(dedup_regex.copy(), path_part, items)

                filtered_items = []
                for item in items:
                    if item not in filtered_items:
                        filtered_items.append(item)

                dedup_path.append(''.join(filtered_items))

            relpath = Path(*dedup_path)
            files_data.append((copy(media), relpath))

        # Sort files and solve conflicts
        self._sort_medias(files_data, remove_duplicates=remove_duplicates)

        if not self._check_processed():
            self.summary.append('check', False)

        return self.summary

    def _get_images(self, path):
        """
        :returns: iter
        """
        for src_path in self._get_files_in_path(
            path, glob=self.glob,
            extensions=self.filter_by_ext,
        ):
            dirname = src_path.parent.name

            if dirname.find('similar_to') == 0:
                continue

            image = Image(src_path)

            if image.is_image():
                yield image

    def _get_media_data(self, img_path, path):
        media = Media(img_path, path, self.logger)
        media.get_metadata(self.root, db=self.db, cache=self.cache)

        return media

    def _find_similar_images(self, image, images, path, dest_dir, similarity=80):
        files_data = []
        if not image.img_path.is_file():
            return files_data

        name = image.img_path.stem
        directory_name = dest_dir / name.replace('.', '_')

        for img_path in images.find_similar(image, similarity):
            self.src_list.append(img_path)

            media = self._get_media_data(img_path, path)
            relpath = directory_name / img_path.name

            files_data.append((copy(media), relpath))

        if files_data:
            # Found similar images to image
            self.src_list.append(image.img_path)
            media = self._get_media_data(image.img_path, path)
            relpath = directory_name / image.img_path.name
            files_data.insert(0, (copy(media), relpath))

        return files_data

    def sort_similar_images(self, path, similarity=80, remove_duplicates=False):
        """Sort similar images using imagehash library"""
        # Check db
        self._init_check_db()

        dest_dir = self.root / 'similar_images'
        path = self._check_path(path)

        images_paths = set(x for x in self._get_images(path))
        images = Images(images_paths, logger=self.logger)
        nb_row_ini = self.db.len('metadata')
        for image in images_paths:
            files_data = self._find_similar_images(
                image, images, path, dest_dir, similarity
            )
            if files_data:
                # Move the simlars file into the destination directory
                self._sort_medias(files_data, remove_duplicates=remove_duplicates)

        nb_row_end = self.db.len('metadata')
        if nb_row_ini and nb_row_ini != nb_row_end:
            self.logger.error('Nb of row have changed unexpectedly')

        if not self._check_processed():
            self.summary.append('check', False)

        return self.summary

    def fill_data(self, path, key, loc=None, edit=False):
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

        if edit:
            print(f"Edit {key} values:")
        else:
            print(f"Fill empty {key} values:")

        self.src_list = self._get_path_list(path)

        for file_path in self.src_list:
            media = Media(
                file_path,
                self.root,
                self.album_from_folder,
                ignore_tags,
                self.interactive,
                self.logger,
                self.use_date_filename,
                self.use_file_dates,
            )
            metadata = media.get_metadata(self.root, loc, self.db, self.cache)
            print()
            value = media.metadata[key]
            if edit or not value:
                print(f"FILE: '{file_path}'")
            if edit:
                print(f"{key}: '{value}'")
            if edit or not value:
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
                self._add_db_data(media.metadata)
                # Update exif data
                media.set_key_values(key, value)

                self.summary.append('update', False, file_path)

        return self.summary
