"""
General file system methods.
"""
from builtins import object

from copy import copy
from datetime import datetime, timedelta
import filecmp
from fnmatch import fnmatch
import inquirer
import logging
import os
from pathlib import Path, PurePath
import re
import sys
import shutil

from ordigi import media
from ordigi.database import Sqlite
from ordigi.media import Media, get_all_subclasses
from ordigi.images import Image, Images
from ordigi import request
from ordigi.summary import Summary
from ordigi import utils


class Collection(object):
    """Class of the media collection."""

    def __init__(self, root, path_format, album_from_folder=False,
            cache=False, day_begins=0, dry_run=False, exclude=set(),
            filter_by_ext=set(), glob='**/*', interactive=False,
            logger=logging.getLogger(), max_deep=None, mode='copy',
            use_date_filename=False, use_file_dates=False):

        # Attributes
        self.root = Path(root).expanduser().absolute()
        if not self.root.exists():
            logger.error(f'Directory {self.root} does not exist')
            sys.exit(1)

        self.path_format = path_format
        self.db = Sqlite(self.root)

        # Options
        self.album_from_folder = album_from_folder
        self.cache = cache
        self.day_begins = day_begins
        self.dry_run = dry_run
        self.exclude = exclude

        if '%media' in filter_by_ext:
            filter_by_ext.remove('%media')
            self.filter_by_ext = filter_by_ext.union(media.extensions)
        else:
            self.filter_by_ext = filter_by_ext

        self.glob = glob
        self.items = self.get_items()
        self.interactive = interactive
        self.logger = logger
        self.max_deep = max_deep
        self.mode = mode
        # List to store media metadata
        self.medias = []
        self.summary = Summary()
        self.use_date_filename = use_date_filename
        self.use_file_dates = use_file_dates
        self.whitespace_regex = '[ \t\n\r\f\v]+'

        self.src_list = []
        self.dest_list = []

        # Constants
        self.theme = request.load_theme()

    def get_items(self):
        return {
        'album': '{album}',
        'basename': '{basename}',
        'camera_make': '{camera_make}',
        'camera_model': '{camera_model}',
        'city': '{city}',
        'custom': '{".*"}',
        'country': '{country}',
        # 'folder': '{folder[<>]?[-+]?[1-9]?}',
        'ext': '{ext}',
        'folder': '{folder}',
        'folders': r'{folders(\[[0-9:]{0,3}\])?}',
        'location': '{location}',
        'name': '{name}',
        'original_name': '{original_name}',
        'state': '{state}',
        'title': '{title}',
        'date': '{(%[a-zA-Z][^a-zA-Z]*){1,8}}' # search for date format string
            }

    def _check_for_early_morning_photos(self, date):
        """check for early hour photos to be grouped with previous day"""
        if date.hour < self.day_begins:
            self.logger.info("moving this photo to the previous day for classification purposes")
            # push it to the day before for classification purposes
            date = date - timedelta(hours=date.hour+1)

        return date

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
        basename = os.path.splitext(metadata['filename'])[0]
        if item == 'basename':
            part = basename
        elif item == 'ext':
            part = os.path.splitext(metadata['filename'])[1][1:]
        elif item == 'name':
            # Remove date prefix added to the name.
            part = basename
            for i, rx in utils.get_date_regex(basename):
                part = re.sub(rx, '', part)
        elif item == 'date':
            date = metadata['date_media']
            # early morning photos can be grouped with previous day
            if date is not None:
                date = self._check_for_early_morning_photos(date)
                part = date.strftime(mask)
        elif item == 'folder':
            part = os.path.basename(metadata['subdirs'])

        elif item == 'folders':
            folders = Path(metadata['subdirs']).parts
            folders = self._get_folders(folders, mask)
            part = os.path.join(*folders)

        elif item in ('album','camera_make', 'camera_model', 'city', 'country',
                 'location', 'original_name', 'state', 'title'):
            if item == 'location':
                mask = 'default'

            if metadata[mask]:
                part = metadata[mask]
        elif item in 'custom':
            # Fallback string
            part = mask[1:-1]

        return part

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
                    # Capitalization
                    u_regex = '%u' + regex
                    l_regex = '%l' + regex
                    if re.search(u_regex, this_part):
                        this_part = re.sub(u_regex, part.upper(), this_part)
                    elif re.search(l_regex, this_part):
                        this_part = re.sub(l_regex, part.lower(), this_part)
                    else:
                        this_part = re.sub(regex, part, this_part)

        # Delete separator char at the begining of the string if any:
        if this_part:
            regex = '[-_ .]'
            if re.match(regex, this_part[0]):
                this_part = this_part[1:]

        return this_part

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
                this_part = self.get_path_part(this_part, metadata)

                if this_part:
                    # Check if all masks are substituted
                    if True in [c in this_part for c in '{}']:
                        self.logger.error(f'Format path part invalid: \
                                {this_part}')
                        sys.exit(1)

                    path.append(this_part.strip())
                    # We break as soon as we have a value to append
                    break
                # Else we continue for fallbacks

        if path == []:
            path = [ metadata['filename'] ]
        elif len(path[-1]) == 0 or re.match(r'^\..*', path[-1]):
            path[-1] = metadata['filename']

        path_string = os.path.join(*path)

        if whitespace_sub != ' ':
            # Lastly we want to sanitize the name
            path_string = re.sub(self.whitespace_regex, whitespace_sub, path_string)

        return path_string

        return None

    def _checkcomp(self, dest_path, src_checksum):
        """Check file.
        """
        if self.dry_run:
            return True

        dest_checksum = utils.checksum(dest_path)

        if dest_checksum != src_checksum:
            self.logger.info(f'Source checksum and destination checksum are not the same')
            return False

        return True

    def _format_row_data(self, table, metadata):
        row_data = {}
        for title in self.db.tables[table]['header']:
            key = utils.camel2snake(title)
            # Convert Path type to str
            row_data[title] = metadata[key]

        return row_data

    def _add_db_data(self, dest_path, metadata):
        loc_values = self._format_row_data('location', metadata)
        metadata['location_id'] = self.db.add_row('location', loc_values)

        row_data = self._format_row_data('metadata', metadata)
        self.db.add_row('metadata', row_data)

    def _update_exif_data(self, dest_path, media):
        updated = False
        if self.album_from_folder:
            media.set_album_from_folder()
            updated = True
        if  media.metadata['original_name'] in (False, ''):
            media.set_value('original_name', self.filename)
            updated = True
        if self.album_from_folder:
            album = media.metadata['album']
            if album and album != '':
                media.set_value('album', album)
                updated = True

        if updated:
            return True

        return False

    def _record_file(self, src_path, dest_path, media):
        """Check file and record the file to db"""

        # Check if file remain the same
        record = False
        checksum = media.metadata['checksum']
        if self._checkcomp(dest_path, checksum):
            # change media file_path to dest_path
            media.file_path = dest_path
            if not self.dry_run:
                updated = self._update_exif_data(dest_path, media)
                if updated:
                    checksum = utils.checksum(dest_path)
                    media.metadata['checksum'] = checksum

                media.metadata['file_path'] = os.path.relpath(dest_path,
                        self.root)
                self._add_db_data(dest_path, media.metadata)

            self.summary.append((src_path, dest_path))
            record = True

        else:
            self.logger.error(f'Files {src_path} and {dest_path} are not identical')
            self.summary.append((src_path, False))

        return record

    def remove(self, file_path):
        if not self.dry_run:
            os.remove(file_path)
        self.logger.info(f'remove: {file_path}')

    def sort_file(self, src_path, dest_path, remove_duplicates=False):
        '''
        Copy or move file to dest_path.
        Return True if success, None is no filesystem action, False if
        conflicts.
        :params: str, str, bool
        :returns: bool or None
        '''

        mode = self.mode
        dry_run = self.dry_run

        # check for collisions
        if(src_path == dest_path):
            self.logger.info(f'File {dest_path} already sorted')
            return None
        elif dest_path.is_dir():
            self.logger.warning(f'File {dest_path} is a existing directory')
            return False
        elif dest_path.is_file():
            self.logger.warning(f'File {dest_path} already exist')
            if remove_duplicates:
                if filecmp.cmp(src_path, dest_path):
                    self.logger.info(f'File in source and destination are identical. Duplicate will be ignored.')
                    if(mode == 'move'):
                        self.remove(src_path)
                    return None
                else:  # name is same, but file is different
                    self.logger.warning(f'File in source and destination are different.')
                    return False
            else:
                return False
        else:
            if(mode == 'move'):
                if not dry_run:
                    # Move the processed file into the destination directory
                    shutil.move(src_path, dest_path)
                self.logger.info(f'move: {src_path} -> {dest_path}')
            elif mode == 'copy':
                if not dry_run:
                    shutil.copy2(src_path, dest_path)
                self.logger.info(f'copy: {src_path} -> {dest_path}')
            return True

    def _solve_conflicts(self, conflict_file_list, remove_duplicates):
        result = False
        unresolved_conflicts = []
        while conflict_file_list != []:
            src_path, dest_path, media = conflict_file_list.pop()
            # Try to sort the file
            result = self.sort_file(src_path, dest_path, remove_duplicates)
            # remove to conflict file list if file as be successfully copied or ignored
            n = 1
            while result is False and n < 100:
                # Add appendix to the name
                suffix = dest_path.suffix
                if n > 1:
                    stem = dest_path.stem.rsplit('_' + str(n-1))[0]
                else:
                    stem = dest_path.stem
                dest_path = dest_path.parent / (stem + '_' + str(n) + suffix)
                result = self.sort_file(src_path, dest_path, remove_duplicates)
                n = n + 1

            record = False
            if result is True:
                record = self._record_file(src_path, dest_path, media)
            elif result is None:
                record = True
            else:
                # n > 100:
                unresolved_conflicts.append((src_path, dest_path, media))
                self.logger.error(f'{self.mode}: too many append for {dest_path}...')
                self.summary.append((src_path, False))

            if record:
                # result is true or None
                self.dest_list.append(dest_path)

        return record

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
                        parts[n-1] = parts[n-1] + part[0]
                    items.append(part[1:])
                else:
                    items.append(part)
            elif dedup_regex != []:
                # Others parts
                self._split_part(dedup_regex, part, items)
            else:
                items.append(part)

        return items

    def walklevel(self, src_path, maxlevel=None):
        """
        Walk into input directory recursively until desired maxlevel
        source: https://stackoverflow.com/questions/229186/os-walk-without-digging-into-directories-below
        """
        src_path = str(src_path)
        if not os.path.isdir(src_path):
            return None

        num_sep = src_path.count(os.path.sep)
        for root, dirs, files in os.walk(src_path):
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

    def _get_files_in_path(self, path, glob='**/*', maxlevel=None, extensions=set()):
        """Recursively get files which match a path and extension.

        :param str path string: Path to start recursive file listing
        :param tuple(str) extensions: File extensions to include (whitelist)
        :returns: Path file_path, Path subdirs
        """
        for path0 in path.glob(glob):
            if path0.is_dir(): continue
            else:
                file_path = path0
                parts = file_path.parts
                subdirs = file_path.relative_to(path).parent
                if glob == '*':
                    level = 0
                else:
                    level = len(subdirs.parts)

                if subdirs.parts != ():
                    if subdirs.parts[0] == '.ordigi': continue

                if maxlevel is not None:
                    if level > maxlevel: continue

                matched = False
                for exclude in self.exclude:
                    if fnmatch(file_path, exclude):
                        matched = True
                        break

                if matched: continue

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
            dir_path = self.root / Path(*parts[0:i+1])
            if dir_path.is_file():
                self.logger.warning(f'Target directory {dir_path} is a file')
                # Rename the src_file
                if self.interactive:
                    prompt = [
                            inquirer.Text('file_path', message="New name for"\
                                f"'{dir_path.name}' file"),
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
        """ Set the modification time on the file based on the file name.
        """

        # Initialize date taken to what's returned from the metadata function.
        os.utime(file_path, (int(datetime.now().timestamp()), int(date_media.timestamp())))

    def dedup_regex(self, path, dedup_regex, remove_duplicates=False):
        # cycle throught files
        result = False
        path = self._check_path(path)
        # Delimiter regex
        delim = r'[-_ .]'
        # Numeric date item  regex
        d = r'\d{2}'
        # Numeric date regex

        if len(dedup_regex) == 0:
            date_num2 = re.compile(fr'([^0-9]{d}{delim}{d}{delim}|{delim}{d}{delim}{d}[^0-9])')
            date_num3 = re.compile(fr'([^0-9]{d}{delim}{d}{delim}{d}{delim}|{delim}{d}{delim}{d}{delim}{d}[^0-9])')
            default = re.compile(r'([^-_ .]+[-_ .])')
            dedup_regex = [
                date_num3,
                date_num2,
                default
            ]

        conflict_file_list = []
        self.src_list = [x for x in self._get_files_in_path(path, glob=self.glob)]
        for src_path in self.src_list:
            # TODO to test it
            media = Media(src_path, path, logger=self.logger)
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

            # Dedup path
            dest_path = self.root.joinpath(*dedup_path)
            self._create_directory(dest_path.parent.name, media)

            result = self.sort_file(src_path, dest_path, remove_duplicates)

            record = False
            if result is True:
                record = self._record_file(src_path, dest_path, media)
            elif result is None:
                record = True
            else:
                # There is conflict files
                conflict_file_list.append(src_path, dest_path, copy(media))

            if record:
                # result is true or None
                self.dest_list.append(dest_path)

        if conflict_file_list != []:
            record = self._solve_conflicts(conflict_file_list, remove_duplicates)

        if not self._check_processed():
            return False

        return self.summary, record

    def _modify_selection(self):
        """
        :params: list
        :return: list
        """
        message="Bellow the file selection list, modify selection if needed"
        questions = [
            inquirer.Checkbox('selection',
                            message=message,
                            choices=self.src_list,
                            default=self.src_list,
                            ),
        ]
        return inquirer.prompt(questions, theme=self.theme)['selection']

    def _check_processed(self):
        # Finally check if are files are successfully processed
        n_fail = len(self.src_list) - len(self.dest_list)
        if n_fail != 0:
            self.logger.error("{n_fail} files have not be processed")
            return False

        return True

    def sort_files(self, paths, loc, remove_duplicates=False,
            ignore_tags=set()):
        """
        Sort files into appropriate folder
        """
        result = False
        files_data = []
        for path in paths:
            self.dest_list = []
            path = self._check_path(path)
            conflict_file_list = []
            self.src_list = [x for x in self._get_files_in_path(path,
                glob=self.glob, extensions=self.filter_by_ext)]
            if self.interactive:
                self.src_list = self._modify_selection()
                print('Processing...')

            # Get medias and paths
            for src_path in self.src_list:
                # Process files
                media = Media(src_path, path, self.album_from_folder,
                        ignore_tags, self.interactive, self.logger,
                        self.use_date_filename, self.use_file_dates)
                metadata = media.get_metadata(self.root, loc, self.db, self.cache)
                # Get the destination path according to metadata
                relpath = Path(self.get_path(metadata))

                files_data.append((copy(media), relpath))

            # Create directories
            for media, relpath in files_data:
                dest_directory = self.root / relpath.parent
                self._create_directory(dest_directory, media)

            # sort files and solve conflicts
            for media, relpath in files_data:
                # Convert paths to string
                src_path = media.file_path
                dest_path = self.root / relpath

                result = self.sort_file(src_path, dest_path, remove_duplicates)


                record = False
                if result is True:
                    record = self._record_file(src_path, dest_path, media)
                elif result is None:
                    record = True
                else:
                    # There is conflict files
                    conflict_file_list.append((src_path, dest_path, media))
                if record:
                    # result is true or None
                    self.dest_list.append(dest_path)

            if conflict_file_list != []:
                record = self._solve_conflicts(conflict_file_list, remove_duplicates)

            if not self._check_processed():
                record = False

        return self.summary, record

    def move_file(self, img_path, dest_path):
        if not self.dry_run:
            shutil.move(img_path, dest_path)

        self.logger.info(f'move: {img_path} -> {dest_path}')

    def _get_images(self, path):
        """
        :returns: iter
        """
        for src_path in self._get_files_in_path(path, glob=self.glob,
                extensions=self.filter_by_ext):
            dirname = src_path.parent.name

            if dirname.find('similar_to') == 0:
                continue

            image = Image(src_path)

            if image.is_image():
                yield image

    def sort_similar_images(self, path, similarity=80):

        result = True
        path = self._check_path(path)
        images = set([ x for x in self._get_images(path) ])
        i = Images(images, logger=self.logger)
        for image in images:
            if not image.img_path.is_file():
                continue
            media_ref = Media(image.img_path, path, self.logger)
            # Todo: compare metadata?
            metadata = media_ref.get_metadata(self.root, db=self.db, cache=self.cache)
            similar = False
            moved_imgs = set()
            for img_path in i.find_similar(image, similarity):
                similar = True
                media = Media(img_path, path, self.logger)
                metadata = media.get_metadata(self.root, db=self.db, cache=self.cache)
                # move image into directory
                name = img_path.stem
                directory_name = 'similar_to_' + name
                dest_directory = img_path.parent / directory_name
                dest_path = dest_directory / img_path.name
                dest_directory.mkdir(exist_ok=True)

                # Move the simlars file into the destination directory
                self.move_file(img_path, dest_path)
                moved_imgs.add(img_path)
                if self._record_file(img_path, dest_path, media):
                    self.summary.append((img_path, dest_path))
                else:
                    self.summary.append((img_path, False))
                    result = False

            if similar:
                img_path = image.img_path
                dest_path = dest_directory / img_path.name
                self.move_file(img_path, dest_path)
                moved_imgs.add(img_path)
                if self._record_file(img_path, dest_path, media_ref):
                    self.summary.append((img_path, dest_path))
                else:
                    self.summary.append((img_path, False))
                    result = False

        return self.summary, result

    def revert_compare(self, path):

        result = True
        path = self._check_path(path)
        dirnames = set()
        moved_files = set()
        for src_path in self._get_files_in_path(path, glob=self.glob,
                extensions=self.filter_by_ext):
            dirname = src_path.parent.name
            if dirname.find('similar_to') == 0:
                dirnames.add(src_path.parent)

                # move file to initial folder and update metadata
                media = Media(src_path, path, self.logger)
                metadata = media.get_metadata(self.root, db=self.db, cache=self.cache)
                dest_path = Path(src_path.parent.parent, src_path.name)
                self.move_file(src_path, dest_path)
                moved_files.add(src_path)
                if self._record_file(src_path, dest_path, media):
                    self.summary.append((src_path, dest_path))
                else:
                    self.summary.append((src_path, False))
                    result = False

        for dirname in dirnames:
            # remove 'similar_to*' directories
            try:
                dirname.rmdir()
            except OSError as error:
                self.logger.error(error)

        return self.summary, result


