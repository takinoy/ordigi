"""
General file system methods.
"""
from builtins import object

import filecmp
from fnmatch import fnmatch
import hashlib
import inquirer
import logging
import os
from pathlib import Path, PurePath
import re
import sys
import shutil
from datetime import datetime, timedelta

from ordigi import media
from ordigi.database import Sqlite
from ordigi.media import Media, get_all_subclasses
from ordigi.images import Image, Images
from ordigi import request
from ordigi.summary import Summary
from ordigi.utils import get_date_regex, camel2snake


class Collection(object):
    """Class of the media collection."""

    def __init__(self, root, path_format, album_from_folder=False,
            cache=False, day_begins=0, dry_run=False, exclude=set(),
            filter_by_ext=set(), glob='**/*', interactive=False,
            logger=logging.getLogger(), max_deep=None, mode='copy'):

        # Attributes
        self.root = Path(root).expanduser().absolute()
        if not os.path.exists(self.root):
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

        self.summary = Summary()
        self.whitespace_regex = '[ \t\n\r\f\v]+'

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

    def check_for_early_morning_photos(self, date):
        """check for early hour photos to be grouped with previous day"""

        if date.hour < self.day_begins:
            self.logger.info('moving this photo to the previous day for\
                    classification purposes (day_begins=' + str(self.day_begins) + ')')
            date = date - timedelta(hours=date.hour+1)  # push it to the day before for classificiation purposes

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

    def get_part(self, item, mask, metadata, subdirs):
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
            for i, rx in get_date_regex(basename):
                part = re.sub(rx, '', part)
        elif item == 'date':
            date = metadata['date_taken']
            # early morning photos can be grouped with previous day
            date = self.check_for_early_morning_photos(date)
            if date is not None:
                part = date.strftime(mask)
        elif item == 'folder':
            part = os.path.basename(subdirs)

        elif item == 'folders':
            folders = subdirs.parts
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

    def get_path_part(self, this_part, metadata, subdirs):
        """Build path part
        :returns: part (string)"""
        for item, regex in self.items.items():
            matched = re.search(regex, this_part)
            if matched:
                part = self.get_part(item, matched.group()[1:-1], metadata,
                        subdirs)

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

        return this_part

    def get_path(self, metadata, subdirs, whitespace_sub='_'):
        """path_format: {%Y-%d-%m}/%u{city}/{album}

        Returns file path.

        :returns: string"""

        path_format = self.path_format
        path = []
        path_parts = path_format.split('/')
        for path_part in path_parts:
            this_parts = path_part.split('|')
            for this_part in this_parts:
                this_part = self.get_path_part(this_part, metadata, subdirs)

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

        if len(path[-1]) == 0 or re.match(r'^\..*', path[-1]):
            path[-1] = metadata['filename']

        path_string = os.path.join(*path)

        if whitespace_sub != ' ':
            # Lastly we want to sanitize the name
            path_string = re.sub(self.whitespace_regex, whitespace_sub, path_string)

        return path_string

        return None

    def checksum(self, file_path, blocksize=65536):
        """Create a hash value for the given file.

        See http://stackoverflow.com/a/3431835/1318758.

        :param str file_path: Path to the file to create a hash for.
        :param int blocksize: Read blocks of this size from the file when
            creating the hash.
        :returns: str or None
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            buf = f.read(blocksize)

            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(blocksize)
            return hasher.hexdigest()
        return None

    def checkcomp(self, dest_path, src_checksum):
        """Check file.
        """
        # src_checksum = self.checksum(src_path)

        if self.dry_run:
            return src_checksum

        dest_checksum = self.checksum(dest_path)

        if dest_checksum != src_checksum:
            self.logger.info(f'Source checksum and destination checksum are not the same')
            return False

        return src_checksum

    def _get_row_data(self, table, metadata):
        row_data = {}
        for title in self.db.tables[table]['header']:
            key = camel2snake(title)
            row_data[title] = metadata[key]

        return row_data

    def _add_db_data(self, dest_path, metadata):
        loc_values = self._get_row_data('location', metadata)
        metadata['location_id'] = self.db.add_row('location', loc_values)

        row_data = self._get_row_data('metadata', metadata)
        self.db.add_row('metadata', row_data)

    def _update_exif_data(self, dest_path, media):
        if self.album_from_folder:
            media.file_path = dest_path
            media.set_album_from_folder()
            return True

        return False

    def record_file(self, src_path, dest_path, src_checksum, media):
        """Check file and record the file to db"""

        # Check if file remain the same
        checksum = self.checkcomp(dest_path, src_checksum)
        has_errors = False
        if checksum:
            if not self.dry_run:
                updated = self._update_exif_data(dest_path, media)
                if updated:
                    dest_checksum = self.checksum(dest_path)

                media.metadata['file_path'] = os.path.relpath(dest_path,
                        self.root)
                media.metadata['checksum'] = checksum
                self._add_db_data(dest_path, media.metadata)

            self.summary.append((src_path, dest_path))

        else:
            self.logger.error(f'Files {src_path} and {dest_path} are not identical')
            # sys.exit(1)
            self.summary.append((src_path, False))
            has_errors = True

        return self.summary, has_errors

    def remove(self, file_path):
        if not self.dry_run:
            os.remove(file_path)
        self.logger.info(f'remove: {file_path}')

    def sort_file(self, src_path, dest_path, remove_duplicates=False):
        '''Copy or move file to dest_path.'''

        mode = self.mode
        dry_run = self.dry_run

        # check for collisions
        if(src_path == dest_path):
            self.logger.info(f'File {dest_path} already sorted')
            return None
        elif os.path.isfile(dest_path):
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

    def _solve_conflicts(self, conflict_file_list, media, remove_duplicates):
        has_errors = False
        unresolved_conflicts = []
        while conflict_file_list != []:
            file_paths = conflict_file_list.pop()
            src_path = file_paths['src_path']
            src_checksum = file_paths['src_checksum']
            dest_path = file_paths['dest_path']
            # Try to sort the file
            result = self.sort_file(src_path, dest_path, remove_duplicates)
            # remove to conflict file list if file as be successfully copied or ignored
            n = 1
            while result is False and n < 100:
                # Add appendix to the name
                pre, ext = os.path.splitext(dest_path)
                if n > 1:
                    regex = '_' + str(n-1) + ext
                    pre = re.split(regex, dest_path)[0]
                dest_path = pre + '_' + str(n) + ext
                # file_list[item]['dest_path'] = dest_path
                file_paths['dest_path'] = dest_path
                result = self.sort_file(src_path, dest_path, remove_duplicates)
                n = n + 1

            if result is False:
                # n > 100:
                unresolved_conflicts.append(file_paths)
                self.logger.error(f'{self.mode}: too many append for {dest_path}...')
                self.summary.append((src_path, False))
                has_errors = True

            if result:
                self.summary, has_errors = self.record_file(src_path,
                    dest_path, src_checksum, media)

        if has_errors:
            return False
        else:
            return True

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
        # if isinstance(path, str):
        #     # To remove trailing '/' chars
        #     path = Path(path)
        # path = str(path)
        return len(path.parts) - 1

    # TODO move to utils.. or CPath..
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

                if file_path.parts[0] == '.ordigi': continue

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

    def _create_directory(self, directory_path):
        """Create a directory if it does not already exist.

        :param Path: A fully qualified path of the to create.
        :returns: bool
        """
        try:
            if directory_path.exists():
                return True
            else:
                if not self.dry_run:
                    directory_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f'Create {directory_path}')
                return True
        except OSError:
            # OSError is thrown for cases like no permission
            pass

        return False

    def create_directory(self, directory_path):
        """Create a directory if it does not already exist.

        :param str directory_name: A fully qualified path of the
            to create.
        :returns: bool
        """
        try:
            if os.path.exists(directory_path):
                return True
            else:
                if not self.dry_run:
                    os.makedirs(directory_path)
                self.logger.info(f'Create {directory_path}')
                return True
        except OSError:
            # OSError is thrown for cases like no permission
            pass

        return False

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

    def check_path(self, path):
        path = os.path.abspath(os.path.expanduser(path))

        # some error checking
        if not os.path.exists(path):
            self.logger.error(f'Directory {path} does not exist')
            sys.exit(1)

        return path

    def set_utime_from_metadata(self, date_taken, file_path):
        """ Set the modification time on the file based on the file name.
        """

        # Initialize date taken to what's returned from the metadata function.
        os.utime(file_path, (int(datetime.now().timestamp()), int(date_taken.timestamp())))

    def dedup_regex(self, path, dedup_regex, logger, remove_duplicates=False):
        # cycle throught files
        has_errors = False
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
        file_list = [x for x in self._get_files_in_path(path, glob=self.glob)]
        for src_path in file_list:
            src_checksum = self.checksum(src_path)
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
            self._create_directory(dest_path.parent.name)

            src_path = str(src_path)
            dest_path = str(dest_path)

            result = self.sort_file(src_path, dest_path, remove_duplicates)
            if result:
                self.summary, has_errors = self.record_file(src_path,
                    dest_path, src_checksum, media)
            elif result is False:
                # There is conflict files
                conflict_file_list.append({'src_path': src_path,
                'src_checksum': src_checksum, 'dest_path': dest_path})

        if conflict_file_list != []:
            result = self._solve_conflicts(conflict_file_list, media, remove_duplicates)

        if not result:
            has_errors = True

        return self.summary, has_errors

    def _modify_selection(self, file_list):
        """
        :params: list
        :return: list
        """
        message="Bellow the file selection list, modify selection if needed"
        questions = [
            inquirer.Checkbox('selection',
                            message=message,
                            choices=file_list,
                            default=file_list,
                            ),
        ]
        return inquirer.prompt(questions, theme=self.theme)['selection']

    def sort_files(self, paths, loc, remove_duplicates=False,
            ignore_tags=set()):
        """
        Sort files into appropriate folder
        """
        has_errors = False
        for path in paths:
            path = self._check_path(path)
            conflict_file_list = []
            file_list = [x for x in self._get_files_in_path(path,
                glob=self.glob, extensions=self.filter_by_ext)]
            if self.interactive:
                file_list = self._modify_selection(file_list)
                print('Processing...')
            for src_path in file_list:
                subdirs = src_path.relative_to(path).parent
                # Process files
                src_checksum = self.checksum(src_path)
                media = Media(src_path, path, self.album_from_folder, ignore_tags,
                        self.interactive, self.logger)
                if media:
                    metadata = media.get_metadata(loc, self.db, self.cache)
                    # Get the destination path according to metadata
                    file_path = Path(self.get_path(metadata, subdirs))
                else:
                    # Keep same directory structure
                    file_path = src_path.relative_to(path)

                dest_directory = self.root / file_path.parent
                self._create_directory(dest_directory)

                # Convert paths to string
                src_path = str(src_path)
                dest_path = str(self.root / file_path)

                result = self.sort_file(src_path, dest_path, remove_duplicates)

                if result:
                    self.summary, has_errors = self.record_file(src_path,
                        dest_path, src_checksum, media)
                elif result is False:
                    # There is conflict files
                    conflict_file_list.append({'src_path': src_path,
                        'src_checksum': src_checksum, 'dest_path': dest_path})

            if conflict_file_list != []:
                result = self._solve_conflicts(conflict_file_list, media,
                       remove_duplicates)

            if not result:
                has_errors = True

            return self.summary, has_errors

    def set_hash(self, result, src_path, dest_path, src_checksum):
        if result:
            # Check if file remain the same
            result = self.checkcomp(dest_path, src_checksum)
            has_errors = False
            if result:
                if not self.dry_run:
                    self._add_db_data(dest_path, metadata, checksum)

                if dest_path:
                    self.logger.info(f'{src_path} -> {dest_path}')

                self.summary.append((src_path, dest_path))

            else:
                self.logger.error(f'Files {src_path} and {dest_path} are not identical')
                # sys.exit(1)
                self.summary.append((src_path, False))
                has_errors = True
        else:
            self.summary.append((src_path, False))
            has_errors = True

        return has_errors

    def move_file(self, img_path, dest_path, checksum):
        if not self.dry_run:
            try:
                shutil.move(img_path, dest_path)
            except OSError as error:
                self.logger.error(error)

        self.logger.info(f'move: {img_path} -> {dest_path}')
        return self.set_hash(True, img_path, dest_path, checksum)

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
                yield src_path

    def sort_similar_images(self, path, similarity=80):

        has_errors = False
        path = self._check_path(path)
        img_paths = set([ x for x in self._get_images(path) ])
        i = Images(img_paths, logger=self.logger)
        for image in img_paths:
            if not os.path.isfile(image):
                continue
            checksum1 = self.checksum(image)
            # Process files
            # media = Media(src_path, False, self.logger)
            # TODO compare metadata
            # if media:
            #     metadata = media.get_metadata()
            similar = False
            moved_imgs = set()
            for img_path in i.find_similar(image, similarity):
                similar = True
                checksum2 = self.checksum(img_path)
                # move image into directory
                name = os.path.splitext(os.path.basename(image))[0]
                directory_name = 'similar_to_' + name
                dest_directory = os.path.join(os.path.dirname(img_path),
                        directory_name)
                dest_path = os.path.join(dest_directory, os.path.basename(img_path))

                result = self.create_directory(dest_directory)
                # Move the simlars file into the destination directory
                if result:
                    result = self.move_file(img_path, dest_path, checksum2)
                    moved_imgs.add(img_path)
                    if not result:
                        has_errors = True
                else:
                    has_errors = True


            if similar:
                dest_path = os.path.join(dest_directory,
                        os.path.basename(image))
                result = self.move_file(image, dest_path, checksum1)
                moved_imgs.add(image)
                if not result:
                    has_errors = True

            # for moved_img in moved_imgs:
            #     os.remove(moved_img)

        return self.summary, has_errors

    def revert_compare(self, path):

        has_errors = False
        path = self.check_path(path)
        for dirname, dirnames, filenames, level in self.walklevel(path, None):
            if dirname == os.path.join(path, '.ordigi'):
                continue
            if dirname.find('similar_to') == 0:
                continue

            for subdir in dirnames:
                if subdir.find('similar_to') == 0:
                    file_names = os.listdir(os.path.abspath(os.path.join(dirname, subdir)))
                    for file_name in file_names:
                        # move file to initial folder
                        img_path = os.path.join(dirname, subdir, file_name)
                        if os.path.isdir(img_path):
                            continue
                        checksum = self.checksum(img_path)
                        dest_path = os.path.join(dirname, os.path.basename(img_path))
                        result = self.move_file(img_path, dest_path, checksum)
                        if not result:
                            has_errors = True
                    # remove directory
                    try:
                        os.rmdir(os.path.join (dirname, subdir))
                    except OSError as error:
                        self.logger.error(error)

        return self.summary, has_errors


