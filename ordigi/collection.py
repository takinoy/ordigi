"""
General file system methods.
"""
from builtins import object

import filecmp
import hashlib
import logging
import os
from pathlib import Path
import re
import sys
import shutil
from datetime import datetime, timedelta

from ordigi import media
from ordigi.media import Media, get_all_subclasses
from ordigi.images import Images
from ordigi.summary import Summary


class Collection(object):
    """Class of the media collection."""

    def __init__(self, path_format, root, cache=False, day_begins=0, dry_run=False, exclude_regex_list=set(),
            filter_by_ext=set(), logger=logging.getLogger(), max_deep=None,
            mode='copy'):

        self.root = root

        self.cache = cache
        self.day_begins = day_begins
        self.dry_run = dry_run
        self.exclude_regex_list = exclude_regex_list

        if '%media' in filter_by_ext:
            filter_by_ext.remove('%media')
            self.filter_by_ext = filter_by_ext.union(media.extensions)
        else:
            self.filter_by_ext = filter_by_ext

        self.items = self.get_items()
        self.logger = logger
        self.max_deep = max_deep
        self.mode = mode
        self.path_format = path_format

        self.summary = Summary()
        self.whitespace_regex = '[ \t\n\r\f\v]+'

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

    def get_date_regex(self, string, user_regex=None):
        if user_regex is not None:
            matches = re.findall(user_regex, string)
        else:
            regex = {
                # regex to match date format type %Y%m%d, %y%m%d, %d%m%Y,
                # etc...
                'a': re.compile(
                    r'.*[_-]?(?P<year>\d{4})[_-]?(?P<month>\d{2})[_-]?(?P<day>\d{2})[_-]?(?P<hour>\d{2})[_-]?(?P<minute>\d{2})[_-]?(?P<second>\d{2})'),
                'b': re.compile (
                    r'[-_./](?P<year>\d{4})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})[-_./]'),
                # not very accurate
                'c': re.compile (
                    r'[-_./](?P<year>\d{2})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})[-_./]'),
                'd': re.compile (
                r'[-_./](?P<day>\d{2})[-_.](?P<month>\d{2})[-_.](?P<year>\d{4})[-_./]')
                }

            for i, rx in regex.items():
                yield i, rx

    def get_location_part(self, mask, part, place_name):
        """Takes a mask for a location and interpolates the actual place names.

        Given these parameters here are the outputs.

        mask = 'city'
        part = 'city-random'
        place_name = {'city': u'Sunnyvale'}
        return 'Sunnyvale'

        mask = 'location'
        part = 'location'
        place_name = {'default': u'Sunnyvale', 'city': u'Sunnyvale'}
        return 'Sunnyvale'

        :returns: str
        """
        folder_name = part
        if(mask in place_name):
            replace_target = mask
            replace_with = place_name[mask]
        else:
            replace_target = part
            replace_with = ''

        folder_name = folder_name.replace(
            replace_target,
            replace_with,
        )

        return folder_name

    def check_for_early_morning_photos(self, date):
        """check for early hour photos to be grouped with previous day"""

        if date.hour < self.day_begins:
            self.logger.info('moving this photo to the previous day for\
                    classification purposes (day_begins=' + str(self.day_begins) + ')')
            date = date - timedelta(hours=date.hour+1)  # push it to the day before for classificiation purposes

        return date

    def get_part(self, item, mask, metadata, db, subdirs, loc):
        """Parse a specific folder's name given a mask and metadata.

        :param item: Name of the item as defined in the path (i.e. date from %date)
        :param mask: Mask representing the template for the path (i.e. %city %state
        :param metadata: Metadata dictionary.
        :returns: str
        """

        # Each item has its own custom logic and we evaluate a single item and return
        # the evaluated string.
        part = ''
        if item == 'basename':
            part = os.path.basename(metadata['base_name'])
        elif item == 'name':
            # Remove date prefix added to the name.
            part = metadata['base_name']
            for i, rx in self.get_date_regex(metadata['base_name']):
                part = re.sub(rx, '', part)
        elif item == 'date':
            date = self.get_date_taken(metadata)
            # early morning photos can be grouped with previous day
            date = self.check_for_early_morning_photos(date)
            if date is not None:
                part = date.strftime(mask)
        elif item in ('location', 'city', 'state', 'country'):
            place_name = loc.place_name(
                metadata['latitude'],
                metadata['longitude'],
                db,
                self.cache,
                self.logger
            )
            if item == 'location':
                mask = 'default'

            part = self.get_location_part(mask, item, place_name)
        elif item == 'folder':
            part = os.path.basename(subdirs)

        elif item == 'folders':
            folders = Path(subdirs).parts
            folders = eval(mask)

            part = os.path.join(*folders)

        elif item in ('album','camera_make', 'camera_model', 'ext',
                 'original_name', 'title'):
            if metadata[item]:
                part = metadata[item]
        elif item in 'custom':
            # Fallback string
            part = mask[1:-1]

        return part

    def get_path_part(self, this_part, metadata, db, subdirs, loc):
        """Build path part
        :returns: part (string)"""
        for item, regex in self.items.items():
            matched = re.search(regex, this_part)
            if matched:
                part = self.get_part(item, matched.group()[1:-1], metadata, db,
                        subdirs, loc)

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

    def get_path(self, metadata, db, loc, subdirs='', whitespace_sub='_'):
        """path_format: {%Y-%d-%m}/%u{city}/{album}

        Returns file path.

        :returns: string"""

        path_format = self.path_format
        path = []
        path_parts = path_format.split('/')
        for path_part in path_parts:
            this_parts = path_part.split('|')
            for this_part in this_parts:
                this_part = self.get_path_part(this_part, metadata, db, subdirs, loc)

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

        if(len(path[-1]) == 0):
            path[-1] = metadata['base_name']

        path_string = os.path.join(*path)

        if whitespace_sub != ' ':
            # Lastly we want to sanitize the name
            path_string = re.sub(self.whitespace_regex, whitespace_sub, path_string)

        return path_string

    def get_date_from_string(self, string, user_regex=None):
        # If missing datetime from EXIF data check if filename is in datetime format.
        # For this use a user provided regex if possible.
        # Otherwise assume a filename such as IMG_20160915_123456.jpg as default.

        matches = []
        for i, rx in self.get_date_regex(string, user_regex):
            match = re.findall(rx, string)
            if match != []:
                if i == 'c':
                    match = [('20' + match[0][0], match[0][1], match[0][2])]
                elif i == 'd':
                    # reorder items
                    match = [(match[0][2], match[0][1], match[0][0])]
                # matches = match + matches
                if len(match) != 1:
                    # The time string is not uniq
                    continue
                matches.append((match[0], rx))
                # We want only the first match for the moment
                break

        # check if there is only one result
        if len(set(matches)) == 1:
            try:
                # Convert str to int
                date_object = tuple(map(int, matches[0][0]))

                time = False
                if len(date_object) > 3:
                    time = True

                date = datetime(*date_object)
            except (KeyError, ValueError):
                return None

            return date

        return None

    def get_date_taken(self, metadata):
        '''
        Get the date taken from metadata or filename
        :returns: datetime or None.
        '''
        if metadata is None:
            return None

        basename = metadata['base_name']
        date_original = metadata['date_original']
        if metadata['original_name'] is not  None:
            date_filename = self.get_date_from_string(metadata['original_name'])
        else:
            date_filename = self.get_date_from_string(basename)

        date_created = metadata['date_created']
        if metadata['date_original'] is not None:
            if (date_filename is not None and
                    date_filename != date_original):
                self.logger.warn(f"{basename} time mark is different from {date_original}")
                # TODO ask for keep date taken, filename time, or neither
            return metadata['date_original']
        elif True:
            if date_filename is not  None:
                if date_created is not None and date_filename > date_created:
                    self.logger.warn(f"{basename} time mark is more recent than {date_created}")
                return date_filename
        if True:
            # TODO warm and ask for confirmation
            if date_created is not  None:
                return date_created
            elif metadata['date_modified'] is not  None:
                return metadata['date_modified']

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

    def check_file(self, src_path, dest_path, src_checksum, db):

        # Check if file remain the same
        checksum = self.checkcomp(dest_path, src_checksum)
        has_errors = False
        if checksum:
            if not self.dry_run:
                db.add_hash(checksum, dest_path)
                db.update_hash_db()

            self.summary.append((src_path, dest_path))

        else:
            self.logger.error(f'Files {src_path} and {dest_path} are not identical')
            # sys.exit(1)
            self.summary.append((src_path, False))
            has_errors = True

        return self.summary, has_errors

    def should_exclude(self, path, regex_list=set(), needs_compiled=False):
        if(len(regex_list) == 0):
            return False

        if(needs_compiled):
            compiled_list = []
            for regex in regex_list:
                compiled_list.append(re.compile(regex))
            regex_list = compiled_list

        return any(regex.search(path) for regex in regex_list)

    def walklevel(self, src_path, maxlevel=None):
        """
        Walk into input directory recursively until desired maxlevel
        source: https://stackoverflow.com/questions/229186/os-walk-without-digging-into-directories-below
        """
        src_path = src_path.rstrip(os.path.sep)
        if not os.path.isdir(src_path):
            return None

        num_sep = src_path.count(os.path.sep)
        for root, dirs, files in os.walk(src_path):
            level = root.count(os.path.sep) - num_sep
            yield root, dirs, files, level
            if maxlevel is not None and level >= maxlevel:
                del dirs[:]

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

    def solve_conflicts(self, conflict_file_list, db, remove_duplicates):
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
                self.summary, has_errors = self.check_file(src_path,
                    dest_path, src_checksum, db)

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

    def get_files_in_path(self, path, extensions=set()):
        """Recursively get files which match a path and extension.

        :param str path string: Path to start recursive file listing
        :param tuple(str) extensions: File extensions to include (whitelist)
        :returns: file_path, subdirs
        """
        file_list = set()
        if os.path.isfile(path):
            if not self.should_exclude(path, self.exclude_regex_list, True):
                file_list.add((path, ''))

        # Create a list of compiled regular expressions to match against the file path
        compiled_regex_list = [re.compile(regex) for regex in self.exclude_regex_list]

        subdirs = ''
        for dirname, dirnames, filenames, level in self.walklevel(path,
                self.max_deep):
            if dirname == os.path.join(path, '.ordigi'):
                continue

            subdirs = os.path.join(subdirs, os.path.basename(dirname))

            for filename in filenames:
                # If file extension is in `extensions` 
                # And if file path is not in exclude regexes
                # Then append to the list
                filename_path = os.path.join(dirname, filename)
                if (
                        extensions == set()
                        or os.path.splitext(filename)[1][1:].lower() in extensions
                        and not self.should_exclude(filename_path, compiled_regex_list, False)
                    ):
                    file_list.add((filename_path, subdirs))

        return file_list

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

    def dedup_regex(self, path, dedup_regex, db, logger, remove_duplicates=False):
        # cycle throught files
        has_errors = False
        path = self.check_path(path)
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
        for src_path, _ in self.get_files_in_path(path):
            src_checksum = self.checksum(src_path)
            file_path = Path(src_path).relative_to(self.root)
            path_parts = file_path.parts
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
            dest_path = os.path.join(self.root, *dedup_path)
            self.create_directory(os.path.dirname(dest_path))

            result = self.sort_file(src_path, dest_path, remove_duplicates)
            if result:
                self.summary, has_errors = self.check_file(src_path,
                        dest_path, src_checksum, db)
            elif result is False:
                # There is conflict files
                conflict_file_list.append({'src_path': src_path,
                'src_checksum': src_checksum, 'dest_path': dest_path})

        if conflict_file_list != []:
            result = self.solve_conflicts(conflict_file_list, db, remove_duplicates)

        if not result:
            has_errors = True

        return self.summary, has_errors

    def sort_files(self, paths, db, loc, remove_duplicates=False,
            ignore_tags=set()):
        """
        Sort files into appropriate folder
        """
        has_errors = False
        for path in paths:
            path = self.check_path(path)
            conflict_file_list = []
            for src_path, subdirs in self.get_files_in_path(path,
                    extensions=self.filter_by_ext):
                # Process files
                src_checksum = self.checksum(src_path)
                media = Media(src_path, ignore_tags, self.logger)
                if media:
                    metadata = media.get_metadata()
                    # Get the destination path according to metadata
                    file_path = self.get_path(metadata, db, loc, subdirs=subdirs)
                else:
                    # Keep same directory structure
                    file_path = os.path.relpath(src_path, path)

                dest_directory = os.path.join(self.root,
                        os.path.dirname(file_path))
                dest_path = os.path.join(self.root, file_path)

                self.create_directory(dest_directory)

                result = self.sort_file(src_path, dest_path, remove_duplicates)

                if result is False:
                    # There is conflict files
                    conflict_file_list.append({'src_path': src_path,
                        'src_checksum': src_checksum, 'dest_path': dest_path})

            if conflict_file_list != []:
                result = self.solve_conflicts(conflict_file_list, db, remove_duplicates)

            if not result:
                has_errors = True

            return self.summary, has_errors

    def set_hash(self, result, src_path, dest_path, src_checksum, db):
        if result:
            # Check if file remain the same
            result = self.checkcomp(dest_path, src_checksum)
            has_errors = False
            if result:
                if not self.dry_run:
                    db.add_hash(checksum, dest_path)
                    db.update_hash_db()

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

    def move_file(self, img_path, dest_path, checksum, db):
        if not self.dry_run:
            try:
                shutil.move(img_path, dest_path)
            except OSError as error:
                self.logger.error(error)

        self.logger.info(f'move: {img_path} -> {dest_path}')
        return self.set_hash(True, img_path, dest_path, checksum, db)

    def sort_similar_images(self, path, db, similarity=80):

        has_errors = False
        path = self.check_path(path)
        for dirname, dirnames, filenames, level in self.walklevel(path, None):
            if dirname == os.path.join(path, '.ordigi'):
                continue
            if dirname.find('similar_to') == 0:
                continue

            file_paths = set()
            for filename in filenames:
                file_paths.add(os.path.join(dirname, filename))

            i = Images(file_paths, logger=self.logger)

            images = set([ i for i in i.get_images() ])
            for image in images:
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
                        result = self.move_file(img_path, dest_path, checksum2, db)
                        moved_imgs.add(img_path)
                        if not result:
                            has_errors = True
                    else:
                        has_errors = True


                if similar:
                    dest_path = os.path.join(dest_directory,
                            os.path.basename(image))
                    result = self.move_file(image, dest_path, checksum1, db)
                    moved_imgs.add(image)
                    if not result:
                        has_errors = True

                # for moved_img in moved_imgs:
                #     os.remove(moved_img)

        return self.summary, has_errors

    def revert_compare(self, path, db):

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
                        result = self.move_file(img_path, dest_path, checksum, db)
                        if not result:
                            has_errors = True
                    # remove directory
                    try:
                        os.rmdir(os.path.join (dirname, subdir))
                    except OSError as error:
                        self.logger.error(error)

        return self.summary, has_errors

