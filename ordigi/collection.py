"""
Collection methods.
"""
from copy import copy
from datetime import datetime, timedelta
from distutils.dir_util import copy_tree
import filecmp
from fnmatch import fnmatch
import os
import re
import shutil
import sys
from pathlib import Path, PurePath

import inquirer

from ordigi import LOG
from ordigi.config import Config
from ordigi.database import Sqlite
from ordigi.media import Medias, WriteExif
from ordigi.images import Image, Images
from ordigi import request
from ordigi.summary import Summary
from ordigi import utils


class FPath:
    """Featured path object"""

    def __init__(self, path_format, day_begins=0):
        self.day_begins = day_begins
        self.items = self.get_items()
        self.log = LOG.getChild(self.__class__.__name__)
        self.path_format = path_format
        self.whitespace_regex = '[ \t\n\r\f\v]+'
        self.whitespace_sub = '_'

    def get_items(self):
        """Return features items of Fpath class"""
        return {
            'album': '<album>',
            'stem': '<stem>',
            'camera_make': '<camera_make>',
            'camera_model': '<camera_model>',
            'city': '<city>',
            'custom': r'<".*">',
            'country': '<country>',
            'date': r'<(%[a-zA-Z][^a-zA-Z]*){1,8}>',  # search for date format string
            'ext': '<ext>',
            'folder': '<folder>',
            'folders': r'<folders(\[[0-9:]{0,3}\])?>',
            'location': '<location>',
            'name': '<name>',
            'original_name': '<original_name>',
            'state': '<state>',
            'title': '<title>',
        }

    def get_early_morning_photos_date(self, date, mask):
        """check for early hour photos to be grouped with previous day"""

        for i in '%H', '%M', '%S', '%I', '%p', '%f':
            # D'ont change date format if datestring contain hour, minutes or seconds.
            if i in mask:
                return date.strftime(mask)

        if date.hour < self.day_begins:
            self.log.info(
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
            regex0 = re.compile(r'[0-9]')
            match = re.search(regex0, mask)
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
            regex0 = re.compile(r'[0-9]:')
            regex1 = re.compile(r':[0-9]')
            begin = int(re.search(regex0, mask)[0][0])
            end = int(re.search(regex1, mask)[0][1])

            if begin > n:
                # no matched folders
                return ['']

            if end > n:
                end = n

            if begin >= end:
                return ['']

            # select matched folders
            return folders[begin:end]

    def get_part(self, item, mask, metadata):
        """
        Parse a specific folder's name given a mask and metadata.
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
            date_filename, regex, sep = utils.get_date_from_string(stem)
            if date_filename:
                part = re.sub(regex, sep, part)
                # Delete separator
                if re.search('^[-_ .]', part):
                    part = part[1:]
        elif item == 'date':
            date = metadata['date_media']
            # early morning photos can be grouped with previous day
            if date is not None:
                part = str(self.get_early_morning_photos_date(date, mask))
        elif item in ('folder', 'folders'):
            folders = Path(metadata['subdirs']).parts
            if folders:
                if item == 'folder':
                    folder = folders[-1]
                    part = folder
                else:
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
            if metadata[mask]:
                part = str(metadata[mask])
        elif item in 'custom':
            # Fallback string
            part = mask[1:-1]

        return part

    def _substitute(self, regex, part, this_part):
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
                self.log.debug(f'item: {item}, mask: <matched.group()[1:-1]>')
                part = self.get_part(item, matched.group()[1:-1], metadata)
                self.log.debug(f'part: {part}')

                part = part.strip()

                if part == '':
                    # delete separator if any
                    regex = '[-_ .]?(%[ul])?' + regex
                    this_part = re.sub(regex, part, this_part)
                else:
                    if self.whitespace_sub != ' ':
                        # Lastly we want to sanitize the name
                        this_part = re.sub(
                            self.whitespace_regex, self.whitespace_sub, this_part
                        )
                    this_part = self._substitute(regex, part, this_part)

        # remove alternate parts inside bracket separated by |
        regex = r'[-_ .]?\<\|\>'
        if re.search(regex, this_part):
            # Delete substitute part and separator if empty
            this_part = re.sub(regex, '', this_part)
        elif re.search(r'\<.*\>', this_part):
            regex = r'\<\|'
            this_part = re.sub(regex, '', this_part)
            regex = r'\|.*\>'
            this_part = re.sub(regex, '', this_part)
            regex = r'\>'
            this_part = re.sub(regex, '', this_part)

        # Delete separator char at the begining of the string if any:
        if this_part:
            regex = '[-_ .]'
            if re.match(regex, this_part[0]):
                this_part = this_part[1:]

            # Remove unwanted chars in filename
            this_part = utils.filename_filter(this_part)

        return this_part

    def get_path(self, metadata: dict) -> list:
        """
        path_format: <%Y-%d-%m>/%u<city>/<album>
        Returns file path.
        """
        path_format = self.path_format

        # Each element in the list represents a folder.
        # Fallback folders are supported and are nested lists.
        path = []
        path_parts = path_format.split('/')
        for path_part in path_parts:
            part = self.get_path_part(path_part, metadata)

            if part != '':
                # Check if all masks are substituted
                if True in [c in part for c in '<>']:
                    self.log.error(
                        f"Format path part invalid: {part}"
                    )
                    sys.exit(1)

                path.append(part)

        # If last path is empty or start with dot
        if part == '' or re.match(r'^\..*', part):
            path.append(utils.filename_filter(metadata['filename']))

        return os.path.join(*path)


class CollectionDb:

    def __init__(self, root):
        self.sqlite = Sqlite(root)

    def _get_row_data(self, table, metadata):
        row_data = {}
        for title in self.sqlite.tables[table]['header']:
            key = utils.camel2snake(title)
            row_data[title] = metadata[key]

        return row_data

    def add_file_data(self, metadata):
        """Save metadata informations to db"""
        if metadata['latitude'] and metadata['longitude']:
            loc_values = self._get_row_data('location', metadata)
            metadata['location_id'] = self.sqlite.upsert_location(loc_values)

        if metadata['file_path']:
            row_data = self._get_row_data('metadata', metadata)
            self.sqlite.upsert_metadata(row_data)


class FileIO:
    """File Input/Ouput operations for collection"""
    def __init__(self, dry_run=False):
        # Options
        self.dry_run = dry_run
        self.log = LOG.getChild(self.__class__.__name__)

    def copy(self, src_path, dest_path):
        if not self.dry_run:
            shutil.copy2(src_path, dest_path)
        self.log.info(f'copy: {src_path} -> {dest_path}')

    def move(self, src_path, dest_path):
        if not self.dry_run:
            # Move the file into the destination directory
            shutil.move(src_path, dest_path)

        self.log.info(f'move: {src_path} -> {dest_path}')

    def remove(self, path):
        if not self.dry_run:
            os.remove(path)

        self.log.info(f'remove: {path}')

    def mkdir(self, directory):
        if not self.dry_run:
            directory.mkdir(exist_ok=True)

        self.log.info(f'create dir: {directory}')

    def rmdir(self, directory):
        if not self.dry_run:
            directory.rmdir()

        self.log.info(f'remove dir: {directory}')


class Paths:
    """Get filtered files paths"""

    def __init__(self, filters, interactive=False):

        self.filters = filters

        self.extensions = self.filters['extensions']
        if not self.extensions:
            self.extensions = set()
        elif '%media' in self.extensions:
            self.extensions.remove('%media')
            self.extensions = self.extensions.union(Medias.extensions)

        self.glob = self.filters['glob']

        self.interactive = interactive
        self.log = LOG.getChild(self.__class__.__name__)
        self.paths_list = []

        # Attributes
        self.theme = request.load_theme()

    def check(self, path):
        """
        Check if path exist
        :param: Path path
        :return: Path path
        """
        if not path.exists():
            self.log.error(f'Path {path} does not exist')
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

        :param Path path: Path to start recursive file listing
        :returns: Path generator File
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

            if self.filters['max_deep'] is not None:
                if level > self.filters['max_deep']:
                    continue

            self.exclude = self.filters['exclude']
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
        prompt = inquirer.prompt(questions, theme=self.theme)
        if prompt:
            return prompt['selection']

        sys.exit()

    def get_paths_list(self, path):
        self.paths_list = list(self.get_files(path))
        if self.interactive:
            self.paths_list = self._modify_selection()
            print('Processing...')

        return self.paths_list


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
        remove_duplicates=False,
    ):

        # Arguments
        self.fileio = fileio
        self.medias = medias
        self.root = root

        # Options
        self.db = db
        self.dry_run = dry_run
        self.interactive = interactive
        self.log = LOG.getChild(self.__class__.__name__)
        self.remove_duplicates = remove_duplicates
        self.summary = Summary(self.root)

        # Attributes
        self.theme = request.load_theme()

    def _checkcomp(self, dest_path, src_checksum):
        """Check file."""
        if self.dry_run:
            return True

        dest_checksum = utils.checksum(dest_path)

        if dest_checksum != src_checksum:
            self.log.info(
                "Source checksum and destination checksum are not the same"
            )
            return False

        return True

    def _record_file(self, src_path, dest_path, metadata, imp=False):
        """Check file and record the file to db"""
        # Check if file remain the same
        checksum = metadata['checksum']
        if not self._checkcomp(dest_path, checksum):
            self.log.error(f'Files {src_path} and {dest_path} are not identical')
            self.summary.append('check', False, src_path, dest_path)
            return False

        # change media file_path to dest_path
        if not self.dry_run:
            updated = self.medias.update_exif_data(metadata, imp)
            if updated:
                checksum = utils.checksum(dest_path)
                metadata['checksum'] = checksum

            self.db.add_file_data(metadata)
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

    def sort_file(self, src_path, dest_path, metadata, imp=False):
        """Sort file and register it to db"""

        if imp == 'copy':
            self.fileio.copy(src_path, dest_path)
        else:
            self.fileio.move(src_path, dest_path)

        if self.db:
            result = self._record_file(
                src_path, dest_path, metadata, imp=imp
            )
        else:
            result = True

        self._set_summary(result, src_path, dest_path, imp)

        return self.summary

    def _create_directories(self):
        """Create a directory if it does not already exist.

        :param Path: A fully qualified path of the to create.
        :returns: bool
        """
        for file_path, metadata in self.medias.datas.items():
            relpath = os.path.dirname(metadata['file_path'])
            directory_path = self.root / relpath
            parts = directory_path.relative_to(self.root).parts
            for i, _ in enumerate(parts):
                dir_path = self.root / Path(*parts[0: i + 1])
                if dir_path.is_file():
                    self.log.warning(f'Target directory {dir_path} is a file')
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

                    self.log.warning(f'Renaming {dir_path} to {file_path}')
                    if not self.dry_run:
                        shutil.move(dir_path, file_path)
                    metadata = self.medias.datas[dir_path]
                    self.medias.datas[file_path] = metadata
                    del(self.medias.datas[dir_path])

            if not self.dry_run:
                directory_path.mkdir(parents=True, exist_ok=True)
            self.log.info(f'Create {directory_path}')

    def check_conflicts(self, src_path, dest_path):
        """
        Check if file can be copied or moved file to dest_path.
        """

        # check for collisions
        if src_path == dest_path:
            self.log.info(f"File {dest_path} already sorted")
            return 2

        if dest_path.is_dir():
            self.log.info(f"File {dest_path} is a existing directory")
            return 1

        if dest_path.is_file():
            self.log.info(f"File {dest_path} already exist")
            if self.remove_duplicates:
                if filecmp.cmp(src_path, dest_path):
                    self.log.info(
                        "File in source and destination are identical. Duplicate will be ignored."
                    )
                    return 3

                # name is same, but file is different
                self.log.info(
                    f"File {src_path} and {dest_path} are different."
                )
                return 1

            return 1

        return 0

    def _solve_conflicts(self, conflicts):
        unresolved_conflicts = []
        while conflicts != []:
            src_path, dest_path, metadata = conflicts.pop()
            # Check for conflict status again in case is has changed

            conflict = self.check_conflicts(src_path, dest_path)

            for i in range(1, 1000):
                if conflict != 1:
                    break

                # Add appendix to the name
                suffix = dest_path.suffix
                if i > 1:
                    stem = dest_path.stem.rsplit('_' + str(i - 1))[0]
                else:
                    stem = dest_path.stem
                dest_path = dest_path.parent / (stem + '_' + str(i) + suffix)
                conflict = self.check_conflicts(src_path, dest_path)

            if conflict == 1:
                # i = 100:
                unresolved_conflicts.append((src_path, dest_path, metadata))
                self.log.error(f"Too many appends for {dest_path}")

            metadata['file_path'] = os.path.relpath(dest_path, self.root)

            yield (src_path, dest_path, metadata), conflict

    def sort_medias(self, imp=False):
        """
        sort files and solve conflicts
        """
        # Create directories
        self._create_directories()

        conflicts = []
        for src_path, metadata in self.medias.datas.items():
            dest_path = self.root / metadata['file_path']

            conflict = self.check_conflicts(src_path, dest_path)

            if not conflict:
                self.sort_file(
                    src_path, dest_path, metadata, imp=imp
                    )
            elif conflict == 1:
                # There is conflict and file are different
                conflicts.append((src_path, dest_path, metadata))
            elif conflict == 3:
                # Same file checksum
                if imp in (False, 'move'):
                    self.fileio.remove(src_path)
            elif conflict == 2:
                # File already sorted
                pass

        if conflicts != []:
            for files_data, conflict in self._solve_conflicts(conflicts):

                src_path, dest_path, metadata = files_data
                if not conflict:
                    self.sort_file(
                        src_path, dest_path, metadata, imp=imp
                        )
                elif conflict == 1:
                    # There is unresolved conflict
                    self._set_summary(False, src_path, dest_path, imp)
                elif conflict == 3:
                    # Same file checksum
                    if imp in (False, 'move'):
                        self.fileio.remove(src_path)
                elif conflict == 2:
                    # File already sorted
                    pass

        return self.summary


class Collection(SortMedias):
    """Class of the media collection."""

    def __init__(self, root, cli_options=None):

        if not cli_options:
            cli_options = {}

        self.root = root
        self.log = LOG.getChild(self.__class__.__name__)

        # Get config options
        self.opt, default_options = self.get_config_options()

        # Set client options
        for option, value in cli_options.items():
            for section in self.opt:
                if option in self.opt[section]:
                    if value != default_options[section][option]:
                        if option == 'exclude':
                            self.opt[section][option].union(set(value))
                        elif option in ('ignore_tags', 'extensions'):
                            self.opt[section][option] = set(value)
                        else:
                            self.opt[section][option] = value
                        break

        self.exclude = self.opt['Filters']['exclude']
        if not self.exclude:
            self.exclude = set()

        self.fileio = FileIO(self.opt['Terminal']['dry_run'])

        self.root_is_valid()

        self.db = CollectionDb(root)
        self.paths = Paths(
            self.opt['Filters'],
            interactive=self.opt['Terminal']['interactive'],
        )

        self.medias = Medias(
            self.paths,
            root,
            self.opt['Exif'],
            self.db,
            self.opt['Terminal']['interactive'],
        )

        # Features
        super().__init__(
            self.fileio,
            self.medias,
            root,
            self.db,
            self.opt['Terminal']['dry_run'],
            self.opt['Terminal']['interactive'],
            self.opt['Filters']['remove_duplicates'],
        )

        # Attributes
        self.summary = Summary(self.root)
        self.theme = request.load_theme()

    def root_is_valid(self):
        """Check if collection path is valid"""
        if self.root.exists():
            if not self.root.is_dir():
                self.log.error(f'Collection path {self.root} is not a directory')
                sys.exit(1)
        else:
            self.log.error(f'Collection path {self.root} does not exist')
            sys.exit(1)

    def get_config_options(self):
        """Get collection config"""
        config = Config(self.root.joinpath('.ordigi', 'ordigi.conf'))

        return config.get_config_options(), config.get_default_options()

    def _set_option(self, section, option, cli_option):
        """if client option is set overwrite collection option value"""
        if cli_option:
            self.opt[section][option] = cli_option

    def get_collection_files(self, exclude=True):
        if exclude:
            exclude = self.exclude

        paths = Paths(
            filters={
                'exclude': exclude,
                'extensions': None,
                'glob': '**/*',
                'max_deep': None,
            },
            interactive=self.opt['Terminal']['interactive'],
        )
        for file_path in paths.get_files(self.root):
            yield file_path

    def init(self, loc):
        """Init collection db"""
        for file_path in self.get_collection_files():
            metadata = self.medias.get_metadata(file_path, self.root, loc=loc)
            metadata['file_path'] = os.path.relpath(file_path, self.root)

            self.db.add_file_data(metadata)
            self.summary.append('update', True, file_path)

        return self.summary

    def check_files(self):
        """Check file integrity."""
        for file_path in self.paths.get_files(self.root):
            checksum = utils.checksum(file_path)
            relpath = file_path.relative_to(self.root)
            if checksum == self.db.sqlite.get_checksum(relpath):
                self.summary.append('check', True, file_path)
            else:
                self.log.error(f'{file_path} is corrupted')
                self.summary.append('check', False, file_path)

        return self.summary

    def file_in_db(self, file_path, db_rows):
        # Assuming file_path are inside collection root dir
        relpath = os.path.relpath(file_path, self.root)

        # If file not in database
        if relpath not in db_rows:
            return False

        return True

    def _check_file(self, file_path, file_checksum):
        """Check if file checksum as changed"""
        relpath = os.path.relpath(file_path, self.root)
        db_checksum = self.db.sqlite.get_checksum(relpath)
        # Check if checksum match
        if not db_checksum:
            return None

        if db_checksum != file_checksum:
            self.log.warning(f'{file_path} checksum as changed')
            self.log.info(
                f'file_checksum={file_checksum},\ndb_checksum={db_checksum}'
            )
            return False

        return True

    def check_db(self):
        """
        Check if db FilePath match to collection filesystem
        :returns: bool
        """
        file_paths = list(self.get_collection_files())
        db_rows = [row['FilePath'] for row in self.db.sqlite.get_rows('metadata')]
        for file_path in file_paths:
            result = self.file_in_db(file_path, db_rows)
            checksum = utils.checksum(file_path)
            if not result:
                self.log.error('Db data is not accurate')
                self.log.info(f'{file_path} not in db')
                return False
            elif not self._check_file(file_path, checksum):
                # We d'ont want to silently ignore or correct this without
                # resetting the cache as is could be due to file corruption
                self.log.error(f'modified or corrupted file.')
                self.log.info(
                    'Use ordigi update --checksum or --reset-cache, check database integrity or try to restore the file'
                )
                return False

        nb_files = len(file_paths)
        nb_row = len(db_rows)
        if nb_row != nb_files:
            self.log.error('Db data is not accurate')
            return False

        return True

    def check(self):
        if self.db.sqlite.is_empty('metadata'):
            self.log.error('Db data does not exist run `ordigi init`')
            sys.exit(1)
        elif not self.check_db():
            self.log.error('Db data is not accurate run `ordigi update`')
            sys.exit(1)

    def _init_check_db(self, loc=None):
        if self.db.sqlite.is_empty('metadata'):
            self.init(loc)
        elif not self.check_db():
            self.log.error('Db data is not accurate run `ordigi update`')
            sys.exit(1)

    def clone(self, dest_path):
        """Clone collection in another location"""
        self.check()

        if not self.dry_run:
            copy_tree(str(self.root), str(dest_path))

        self.log.info(f'copy: {self.root} -> {dest_path}')

        if not self.dry_run:
            dest_collection = Collection(
                dest_path, {'cache': True, 'dry_run': self.dry_run}
            )

            if not dest_collection.check_db():
                self.summary.append('check', False)

        return self.summary

    def update(self, loc, update_checksum=False):
        """Update collection db"""
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
            metadata = {}

            checksum = utils.checksum(file_path)
            if not self._check_file(file_path, checksum) and update_checksum:
                # metatata will fill checksum from file
                metadata = self.medias.get_metadata(
                    file_path, self.root, checksum, loc=loc
                )
                metadata['file_path'] = relpath
                # set row attribute to the file
                self.db.add_file_data(metadata)
                self.summary.append('update', file_path)

            # If file not in database
            if relpath not in db_paths:
                metadata = self.medias.get_metadata(file_path, self.root, loc=loc)
                metadata['file_path'] = relpath
                # Check if file checksum is in invalid rows
                row = []
                for row in invalid_db_rows:
                    if row['Checksum'] == metadata['checksum']:
                        # file have been moved without registering to db
                        metadata['src_path'] = row['SrcPath']
                        # Check if row FilePath is a subpath of relpath
                        if relpath.startswith(row['FilePath']):
                            path = os.path.relpath(relpath, row['FilePath'])
                            metadata['subdirs'] = row['Subdirs'] + path
                        metadata['Filename'] = row['Filename']
                        break
                # set row attribute to the file
                self.db.add_file_data(metadata)
                self.summary.append('update', file_path)

        # Finally delete invalid rows
        for row in invalid_db_rows:
            self.db.sqlite.delete_filepath(row['FilePath'])

        return self.summary

    def set_utime_from_metadata(self, date_media, file_path):
        """Set the modification time on the file based on the file name."""

        # Initialize date taken to what's returned from the metadata function.
        os.utime(
            file_path, (int(datetime.now().timestamp()), int(date_media.timestamp()))
        )

    def remove_excluded_files(self):
        """Remove excluded files in collection"""
        # get all files
        for file_path in self.get_collection_files(exclude=False):
            for exclude in self.exclude:
                if fnmatch(file_path, exclude):
                    self.fileio.remove(file_path)
                    self.summary.append('remove', True, file_path)
                    break

        return self.summary

    def remove_empty_subdirs(self, directories, src_dirs):
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
                self.fileio.rmdir(directory)
                self.log.info(f"remove empty subdir: {directory}")

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
            for i in files:
                fullpath = os.path.join(directory, i)
                if os.path.isdir(fullpath):
                    self.remove_empty_folders(fullpath)

        # if folder empty, delete it
        files = os.listdir(directory)
        if len(files) == 0 and remove_root:
            self.log.info(f"Removing empty folder: {directory}")
            if not self.opt['Terminal']['dry_run']:
                os.rmdir(directory)
            self.summary.append('remove', True, directory)

        return self.summary

    def sort_files(self, src_dirs, loc, imp=False):
        """
        Sort files into appropriate folder
        """
        # Check db
        self._init_check_db(loc)

        path_format = self.opt['Path']['path_format']
        self.log.debug(f'path_format: {path_format}')

        # Get medias data
        subdirs = set()
        for src_path, metadata in self.medias.get_metadatas(src_dirs, imp=imp, loc=loc):
            # Get the destination path according to metadata
            self.log.info(f'src_path: {src_path}')
            fpath = FPath(path_format, self.opt['Path']['day_begins'])
            metadata['file_path'] = fpath.get_path(metadata)
            subdirs.add(src_path.parent)

            self.medias.datas[src_path] = copy(metadata)

        # Sort files and solve conflicts
        self.summary = self.sort_medias(imp)

        if imp != 'copy':
            self.remove_empty_subdirs(subdirs, src_dirs)

        if not self.check_db():
            self.summary.append('check', False)

        return self.summary

    def dedup_path(self, paths, dedup_regex=None):
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
        for src_path, metadata in self.medias.get_metadatas(paths):
            # Deduplicate the path
            path_parts = src_path.relative_to(self.root).parts
            dedup_path = []
            for path_part in path_parts:
                items = utils.split_part(dedup_regex.copy(), path_part)

                filtered_items = []
                for item in items:
                    if item not in filtered_items:
                        filtered_items.append(item)

                dedup_path.append(''.join(filtered_items))

            metadata['file_path'] = os.path.join(*dedup_path)
            self.medias.datas[src_path] = copy(metadata)

        # Sort files and solve conflicts
        self.sort_medias()

        if not self.check_db():
            self.summary.append('check', False)

        return self.summary

    def _find_similar_images(self, image, images, path, dest_dir, similarity=80):
        if not image.img_path.is_file():
            return False

        name = image.img_path.stem
        directory_name = os.path.join(dest_dir, name.replace('.', '_'))

        for img_path in images.find_similar(image, similarity):
            self.paths.paths_list.append(img_path)

            metadata = self.medias.get_metadata(img_path, path)
            relpath = os.path.join(directory_name, img_path.name)
            metadata['file_path'] = relpath
            self.medias.datas[img_path] = copy(metadata)

        if self.medias.datas:
            # Found similar images to image
            self.paths.paths_list.append(image.img_path)
            metadata = self.medias.get_metadata(image.img_path, path)
            relpath = os.path.join(directory_name, image.img_path.name)
            metadata['file_path'] = relpath
            self.medias.datas[image.img_path] = copy(metadata)

        return True

    def sort_similar_images(self, path, similarity=80):
        """Sort similar images using imagehash library"""
        # Check db
        self._init_check_db()

        dest_dir = 'similar_images'
        path = self.paths.check(path)

        images_paths = set(self.paths.get_images(path))
        images = Images(images_paths)
        nb_row_ini = self.db.sqlite.len('metadata')
        for image in images_paths:
            # Clear datas in every loops
            self.medias.datas = {}
            similar_images = self._find_similar_images(
                image, images, path, dest_dir, similarity
            )
            if similar_images:
                # Move the simlars file into the destination directory
                self.sort_medias()

        nb_row_end = self.db.sqlite.len('metadata')
        if nb_row_ini and nb_row_ini != nb_row_end:
            self.log.error('Nb of row have changed unexpectedly')

        if not self.check_db():
            self.summary.append('check', False)

        return self.summary

    def edit_metadata(self, paths, keys, loc=None, overwrite=False):
        """Edit metadata and exif data for given key"""
        self._init_check_db()

        for file_path, media in self.medias.get_medias_datas(paths, loc=loc):
            result = False
            media.metadata['file_path'] = os.path.relpath(file_path, self.root)
            exif = WriteExif(
                file_path,
                media.metadata,
                ignore_tags=self.opt['Exif']['ignore_tags'],
            )

            for key in keys:
                print()
                value = media.metadata[key]
                if overwrite or not value:
                    print(f"FILE: '{file_path}'")
                if overwrite and value:
                    print(f"{key}: '{value}'")
                if overwrite or not value:
                    # Prompt value for given key for file_path
                    prompt = [
                        inquirer.Text('value', message=key),
                    ]
                    answer = inquirer.prompt(prompt, theme=self.theme)
                    # answer = {'value': '03-12-2021 08:12:35'}
                    # Validate value
                    if key in ('date_original', 'date_created', 'date_modified'):
                        # Check date format
                        value = media.get_date_format(answer['value'])
                    else:
                        value = answer['value']
                        while not value.isalnum():
                            if not value: break
                            print("Invalid entry, use alphanumeric chars")
                            value = inquirer.prompt(prompt, theme=self.theme)

                    if value:
                        media.metadata[key] = value
                        if key == 'location':
                            coordinates = loc.coordinates_by_name(value)
                            if coordinates:
                                media.metadata['latitude'] = coordinates['latitude']
                                media.metadata['longitude'] = coordinates['longitude']
                                media.set_location_from_coordinates(loc)

                        # Update exif data
                        if key == 'location':
                            result = exif.set_key_values(
                                'latitude', media.metadata['latitude']
                            )
                            result = exif.set_key_values(
                                'longitude', media.metadata['longitude']
                            )
                        elif key in exif.get_tags().keys():
                            result = exif.set_key_values(key, value)

            # Update checksum
            media.metadata['checksum'] = utils.checksum(file_path)

            # Update database
            self.db.add_file_data(media.metadata)

            if result:
                self.summary.append('update', True, file_path)
            else:
                self.summary.append('update', False, file_path)

        return self.summary
