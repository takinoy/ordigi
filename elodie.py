#!/usr/bin/env python

import os
import re
import sys
import logging
from datetime import datetime

import click
from send2trash import send2trash

# Verify that external dependencies are present first, so the user gets a
# more user-friendly error instead of an ImportError traceback.
from elodie.dependencies import verify_dependencies
if not verify_dependencies():
    sys.exit(1)

from elodie import constants
from elodie import geolocation
from elodie import log
from elodie.compatability import _decode
from elodie import config
from elodie.config import load_config
from elodie.filesystem import FileSystem
from elodie.gui import CompareImageApp
from elodie.localstorage import Db
from elodie.media.media import Media, get_all_subclasses
from elodie.media.audio import Audio
from elodie.media.photo import Photo
from elodie.media.video import Video
from elodie.plugins.plugins import Plugins
from elodie.result import Result
from elodie.summary import Summary
from elodie.external.pyexiftool import ExifTool
from elodie.dependencies import get_exiftool
from elodie import constants

FILESYSTEM = FileSystem()


def print_help(command):
    click.echo(command.get_help(click.Context(sort)))


def import_file(_file, destination, db, album_from_folder, mode, trash, allow_duplicates):

    """Set file metadata and move it to destination.
    """
    if not os.path.exists(_file):
        log.warn('Could not find %s' % _file)
        log.all('{"source":"%s", "error_msg":"Could not find %s"}' %
                  (_file, _file))
        return
    # Check if the source, _file, is a child folder within destination
    elif destination.startswith(os.path.abspath(os.path.dirname(_file))+os.sep):
        log.all('{"source": "%s", "destination": "%s", "error_msg": "Source cannot be in destination"}' % (
            _file, destination))
        return


    media = Media.get_class_by_file(_file, get_all_subclasses())
    if not media:
        log.warn('Not a supported file (%s)' % _file)
        log.all('{"source":"%s", "error_msg":"Not a supported file"}' % _file)
        return

    dest_path = FILESYSTEM.process_file(_file, destination, db,
        media, album_from_folder, mode, allowDuplicate=allow_duplicates)
    if dest_path:
        log.all('%s -> %s' % (_file, dest_path))
    if trash:
        send2trash(_file)

    return dest_path or None


@click.command('batch')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _batch(debug):
    """Run batch() for all plugins.
    """
    constants.debug = debug
    plugins = Plugins()
    plugins.run_batch()


@click.command('import')
@click.option('--destination', type=click.Path(file_okay=False),
              required=True, help='Copy imported files into this directory.')
@click.option('--source', type=click.Path(file_okay=False),
              help='Import files from this directory, if specified.')
@click.option('--file', type=click.Path(dir_okay=False),
              help='Import this file, if specified.')
@click.option('--album-from-folder', default=False, is_flag=True,
              help="Use images' folders as their album names.")
@click.option('--trash', default=False, is_flag=True,
              help='After copying files, move the old files to the trash.')
@click.option('--allow-duplicates', default=False, is_flag=True,
              help='Import the file even if it\'s already been imported.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.option('--dry-run', default=False, is_flag=True,
              help='Dry run only, no change made to the filesystem.')
@click.option('--exclude-regex', default=set(), multiple=True,
              help='Regular expression for directories or files to exclude.')
@click.argument('paths', nargs=-1, type=click.Path())
def _import(destination, source, file, album_from_folder, trash,
        allow_duplicates, debug, dry_run, exclude_regex, paths):
    """Import files or directories by reading their EXIF and organizing them accordingly.
    """
    if dry_run:
        mode = 'dry_run'
    else:
        mode = 'copy'

    constants.debug = debug
    has_errors = False
    result = Result()

    destination = _decode(destination)
    destination = os.path.abspath(os.path.expanduser(destination))

    files = set()
    paths = set(paths)
    if source:
        source = _decode(source)
        paths.add(source)
    if file:
        paths.add(file)

    # if no exclude list was passed in we check if there's a config
    if len(exclude_regex) == 0:
        config = load_config(constants.CONFIG_FILE)
        if 'Exclusions' in config:
            exclude_regex = [value for key, value in config.items('Exclusions')]

    exclude_regex_list = set(exclude_regex)

    for path in paths:
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            files.update(FILESYSTEM.get_all_files(path, False, exclude_regex_list))
        else:
            if not FILESYSTEM.should_exclude(path, exclude_regex_list, True):
                files.add(path)

    # Initialize Db
    if os.path.exists(destination):
        db = Db(destination)

        for current_file in files:
            dest_path = import_file(current_file, destination, db,
                    album_from_folder, mode, trash, allow_duplicates)
            result.append((current_file, dest_path))
            has_errors = has_errors is True or not dest_path
    else:
        result.append((destination, False))
        has_errors = True

    result.write()

    if has_errors:
        sys.exit(1)


@click.command('sort')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.option('--dry-run', default=False, is_flag=True,
              help='Dry run only, no change made to the filesystem.')
@click.option('--destination', '-d', type=click.Path(file_okay=False),
              default=None, help='Sort files into this directory.')
@click.option('--copy', '-c', default=False, is_flag=True,
              help='True if you want files to be copied over from src_dir to\
              dest_dir rather than moved')
@click.option('--exclude-regex', '-e', default=set(), multiple=True,
              help='Regular expression for directories or files to exclude.')
@click.option('--filter-by-ext', '-f', default=set(), multiple=True, help='''Use filename
        extension to filter files for sorting. If value is '*', use
        common media file extension for filtering. Ignored files remain in
        the same directory structure''' )
@click.option('--ignore-tags', '-i', default=set(), multiple=True,
              help='Specific tags or group that will be ignored when\
              searching for file data. Example \'File:FileModifyDate\' or \'Filename\'' )
@click.option('--max-deep', '-m', default=None,
              help='Maximum level to proceed. Number from 0 to desired level.')
@click.option('--remove-duplicates', '-r', default=False, is_flag=True,
              help='True to remove files that are exactly the same in name\
                      and a file hash')
@click.option('--verbose', '-v', default=False, is_flag=True,
              help='True if you want to see details of file processing')
@click.argument('paths', required=True, nargs=-1, type=click.Path())
def _sort(debug, dry_run, destination, copy, exclude_regex, filter_by_ext, ignore_tags,
        max_deep, remove_duplicates, verbose, paths):
    """Sort files or directories by reading their EXIF and organizing them
    according to config.ini preferences.
    """

    if copy:
        mode = 'copy'
    else:
        mode = 'move'

    if debug:
        constants.debug = logging.DEBUG
    elif verbose:
        constants.debug = logging.INFO
    else:
        constants.debug = logging.ERROR

    if max_deep is not None:
        max_deep = int(max_deep)

    logger = logging.getLogger('elodie')
    logger.setLevel(constants.debug)

    if not destination and paths:
        destination = paths[-1]
        paths = paths[0:-1]
    else:
        sys.exit(1)

    paths = set(paths)
    destination = _decode(destination)
    destination = os.path.abspath(os.path.expanduser(destination))

    if not os.path.exists(destination):
        logger.error(f'Directory {destination} does not exist')

    conf = config.load_config(constants.CONFIG_FILE)
    path_format = config.get_path_definition(conf)

    # if no exclude list was passed in we check if there's a config
    if len(exclude_regex) == 0:
        if 'Exclusions' in conf:
            exclude_regex = [value for key, value in conf.items('Exclusions')]

    exclude_regex_list = set(exclude_regex)

    # Initialize Db
    db = Db(destination)

    if 'Directory' in conf and 'day_begins' in conf['Directory']:
        config_directory = conf['Directory']
        day_begins = config_directory['day_begins']
    else:
        day_begins = 0
    filesystem = FileSystem(day_begins, dry_run, exclude_regex_list,
            filter_by_ext, logger, max_deep, mode, path_format)

    summary, has_errors = filesystem.sort_files(paths, destination, db,
            remove_duplicates, ignore_tags)

    if verbose or debug:
        summary.write()

    if has_errors:
        sys.exit(1)


@click.command('generate-db')
@click.option('--path', type=click.Path(file_okay=False),
              required=True, help='Path of your photo library.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _generate_db(path, debug):
    """Regenerate the hash.json database which contains all of the sha256 signatures of media files. The hash.json file is located at ~/.elodie/.
    """
    constants.debug = debug
    result = Result()
    path = os.path.abspath(os.path.expanduser(path))

    if not os.path.isdir(path):
        log.error('path is not a valid directory %s' % path)
        sys.exit(1)

    db = Db(path)
    db.backup_hash_db()
    db.reset_hash_db()

    for current_file in FILESYSTEM.get_all_files(path):
        result.append((current_file, True))
        db.add_hash(db.checksum(current_file), current_file)
        log.progress()

    db.update_hash_db()
    log.progress('', True)
    result.write()


@click.command('verify')
@click.option('--path', type=click.Path(file_okay=False),
              required=True, help='Path of your photo library.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _verify(path, debug):
    constants.debug = debug
    result = Result()
    db = Db(path)
    for checksum, file_path in db.all():
        if not os.path.isfile(file_path):
            result.append((file_path, False))
            log.progress('x')
            continue

        actual_checksum = db.checksum(file_path)
        if checksum == actual_checksum:
            result.append((file_path, True))
            log.progress()
        else:
            result.append((file_path, False))
            log.progress('x')

    log.progress('', True)
    result.write()


def update_location(media, file_path, location_name, db):
    """Update location exif metadata of media.
    """
    location_coords = geolocation.coordinates_by_name(location_name, db)

    if location_coords and 'latitude' in location_coords and \
            'longitude' in location_coords:
        location_status = media.set_location(location_coords[
            'latitude'], location_coords['longitude'], file_path)
        if not location_status:
            log.error('Failed to update location')
            log.all(('{"source":"%s",' % file_path,
                       '"error_msg":"Failed to update location"}'))
            sys.exit(1)
    return True


def update_time(media, file_path, time_string):
    """Update time exif metadata of media.
    """
    time_format = '%Y-%m-%d %H:%M:%S'
    if re.match(r'^\d{4}-\d{2}-\d{2}$', time_string):
        time_string = '%s 00:00:00' % time_string
    elif re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}\d{2}$', time_string):
        msg = ('Invalid time format. Use YYYY-mm-dd hh:ii:ss or YYYY-mm-dd')
        log.error(msg)
        log.all('{"source":"%s", "error_msg":"%s"}' % (file_path, msg))
        sys.exit(1)

    time = datetime.strptime(time_string, time_format)
    media.set_date_original(time, file_path)
    return True


@click.command('update')
@click.option('--album', help='Update the image album.')
@click.option('--location', help=('Update the image location. Location '
                                  'should be the name of a place, like "Las '
                                  'Vegas, NV".'))
@click.option('--time', help=('Update the image time. Time should be in '
                              'YYYY-mm-dd hh:ii:ss or YYYY-mm-dd format.'))
@click.option('--title', help='Update the image title.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.argument('paths', nargs=-1,
                required=True)
def _update(album, location, time, title, paths, debug):
    """Update a file's EXIF. Automatically modifies the file's location and file name accordingly.
    """
    constants.debug = debug
    has_errors = False
    result = Result()

    files = set()
    for path in paths:
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            files.update(FILESYSTEM.get_all_files(path, False))
        else:
            files.add(path)

    for current_file in files:
        if not os.path.exists(current_file):
            has_errors = True
            result.append((current_file, False))
            log.warn('Could not find %s' % current_file)
            log.all('{"source":"%s", "error_msg":"Could not find %s"}' %
                      (current_file, current_file))
            continue

        current_file = os.path.expanduser(current_file)

        # The destination folder structure could contain any number of levels
        #  So we calculate that and traverse up the tree.
        # '/path/to/file/photo.jpg' -> '/path/to/file' ->
        #  ['path','to','file'] -> ['path','to'] -> '/path/to'
        current_directory = os.path.dirname(current_file)
        destination_depth = -1 * len(FILESYSTEM.get_folder_path_definition())
        destination = os.sep.join(
                          os.path.normpath(
                              current_directory
                          ).split(os.sep)[:destination_depth]
                      )

        # Initialize Db
        db = Db(destination)

        media = Media.get_class_by_file(current_file, get_all_subclasses())
        if media is None:
            continue

        updated = False
        if location:
            update_location(media, current_file, location, db)
            updated = True
        if time:
            update_time(media, current_file, time)
            updated = True
        if album:
            media.set_album(album, current_file)
            updated = True

        # Updating a title can be problematic when doing it 2+ times on a file.
        # You would end up with img_001.jpg -> img_001-first-title.jpg ->
        # img_001-first-title-second-title.jpg.
        # To resolve that we have to track the prior title (if there was one.
        # Then we massage the updated_media's metadata['base_name'] to remove
        # the old title.
        # Since FileSystem.get_file_name() relies on base_name it will properly
        #  rename the file by updating the title instead of appending it.
        remove_old_title_from_name = False
        if title:
            # We call get_metadata() to cache it before making any changes
            metadata = media.get_metadata()
            title_update_status = media.set_title(title)
            original_title = metadata['title']
            if title_update_status and original_title:
                # @TODO: We should move this to a shared method since
                # FileSystem.get_file_name() does it too.
                original_title = re.sub(r'\W+', '-', original_title.lower())
                original_base_name = metadata['base_name']
                remove_old_title_from_name = True
            updated = True

        if updated:
            updated_media = Media.get_class_by_file(current_file,
                                                    get_all_subclasses())
            # See comments above on why we have to do this when titles
            # get updated.
            if remove_old_title_from_name and len(original_title) > 0:
                updated_media.get_metadata()
                updated_media.set_metadata_basename(
                    original_base_name.replace('-%s' % original_title, ''))

            dest_path = FILESYSTEM.process_file(current_file, destination, db,
                updated_media, False, mode='move', allowDuplicate=True)
            log.info(u'%s -> %s' % (current_file, dest_path))
            log.all('{"source":"%s", "destination":"%s"}' % (current_file,
                                                               dest_path))
            # If the folder we moved the file out of or its parent are empty
            # we delete it.
            FILESYSTEM.delete_directory_if_empty(os.path.dirname(current_file))
            FILESYSTEM.delete_directory_if_empty(
                os.path.dirname(os.path.dirname(current_file)))
            result.append((current_file, dest_path))
            # Trip has_errors to False if it's already False or dest_path is.
            has_errors = has_errors is True or not dest_path
        else:
            has_errors = False
            result.append((current_file, False))

    result.write()

    if has_errors:
        sys.exit(1)


@click.command('compare')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.option('--dry-run', default=False, is_flag=True,
              help='Dry run only, no change made to the filesystem.')
@click.option('--find-duplicates', '-f', default=False, is_flag=True)
@click.option('--output-dir', '-o', default=False, is_flag=True, help='output\
        dir')
@click.option('--remove-duplicates', '-r', default=False, is_flag=True)
@click.option('--revert-compare', '-R', default=False, is_flag=True, help='Revert\
        compare')
@click.option('--similar-to', '-s', default=False, help='Similar to given\
        image')
@click.option('--similarity', '-S', default=80, help='Similarity level for\
        images')
@click.option('--verbose', '-v', default=False, is_flag=True,
              help='True if you want to see details of file processing')
@click.argument('path', nargs=1, required=True)
def _compare(debug, dry_run, find_duplicates, output_dir, remove_duplicates,
        revert_compare, similar_to, similarity, verbose, path):
    '''Compare files in directories'''

    logger = logging.getLogger('elodie')
    if debug:
        logger.setLevel(logging.DEBUG)
    elif verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.ERROR)

    # Initialize Db
    db = Db(path)

    filesystem = FileSystem(mode='move', dry_run=dry_run, logger=logger)

    if revert_compare:
        summary, has_errors = filesystem.revert_compare(path, db, dry_run)
    else:
        summary, has_errors = filesystem.sort_similar_images(path, db,
                similarity, dry_run)

    if verbose or debug:
        summary.write()

    if has_errors:
        sys.exit(1)


@click.group()
def main():
    pass


main.add_command(_compare)
main.add_command(_import)
main.add_command(_sort)
main.add_command(_update)
main.add_command(_generate_db)
main.add_command(_verify)
main.add_command(_batch)


if __name__ == '__main__':
    #Initialize ExifTool Subprocess
    exiftool_addedargs = [
       u'-config',
        u'"{}"'.format(constants.exiftool_config)
    ]
    with ExifTool(executable_=get_exiftool(), addedargs=exiftool_addedargs) as et:
        main()
