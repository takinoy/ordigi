#!/usr/bin/env python

import os
import re
import sys
from datetime import datetime

import click

from ordigi.config import Config
from ordigi import constants
from ordigi import log
from ordigi.database import Db
from ordigi.filesystem import FileSystem
from ordigi.geolocation import GeoLocation
from ordigi.media import Media, get_all_subclasses
from ordigi.summary import Summary

FILESYSTEM = FileSystem()


def print_help(command):
    click.echo(command.get_help(click.Context(sort)))


@click.command('batch')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _batch(debug):
    """Run batch() for all plugins.
    """
    constants.debug = debug
    plugins = Plugins()
    plugins.run_batch()


@click.command('sort')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.option('--dry-run', default=False, is_flag=True,
              help='Dry run only, no change made to the filesystem.')
@click.option('--destination', '-d', type=click.Path(file_okay=False),
              default=None, help='Sort files into this directory.')
@click.option('--clean', '-C', default=False, is_flag=True,
              help='Clean empty folders')
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
@click.option('--reset-cache', '-R', default=False, is_flag=True,
              help='Regenerate the hash.json and location.json database ')
@click.option('--verbose', '-v', default=False, is_flag=True,
              help='True if you want to see details of file processing')
@click.argument('paths', required=True, nargs=-1, type=click.Path())
def _sort(debug, dry_run, destination, clean, copy, exclude_regex, filter_by_ext, ignore_tags,
        max_deep, remove_duplicates, reset_cache, verbose, paths):
    """Sort files or directories by reading their EXIF and organizing them
    according to ordigi.conf preferences.
    """

    if copy:
        mode = 'copy'
    else:
        mode = 'move'

    logger = log.get_logger(verbose, debug)

    if max_deep is not None:
        max_deep = int(max_deep)

    cache = True
    if reset_cache:
        cache = False

    if not destination and paths:
        destination = paths[-1]
        paths = paths[0:-1]
    else:
        sys.exit(1)

    paths = set(paths)
    filter_by_ext = set(filter_by_ext)

    destination = os.path.abspath(os.path.expanduser(destination))

    if not os.path.exists(destination):
        logger.error(f'Directory {destination} does not exist')

    config = Config(constants.CONFIG_FILE)
    opt = config.get_options()

    # if no exclude list was passed in we check if there's a config
    if len(exclude_regex) == 0:
        exclude_regex = opt['exclude_regex']
    exclude_regex_list = set(exclude_regex)

    # Initialize Db
    db = Db(destination)

    filesystem = FileSystem(cache, opt['day_begins'], dry_run, exclude_regex_list,
            filter_by_ext, logger, max_deep, mode, opt['path_format'])

    loc = GeoLocation(opt['geocoder'], opt['prefer_english_names'], opt['timeout'])

    summary, has_errors = filesystem.sort_files(paths, destination, db,
            loc, remove_duplicates, ignore_tags)

    if clean:
        remove_empty_folders(destination, logger)

    if verbose or debug:
        summary.write()

    if has_errors:
        sys.exit(1)


def remove_empty_folders(path, logger, remove_root=True):
  'Function to remove empty folders'
  if not os.path.isdir(path):
    return

  # remove empty subfolders
  files = os.listdir(path)
  if len(files):
    for f in files:
      fullpath = os.path.join(path, f)
      if os.path.isdir(fullpath):
        remove_empty_folders(fullpath, logger)

  # if folder empty, delete it
  files = os.listdir(path)
  if len(files) == 0 and remove_root:
    logger.info(f"Removing empty folder: {path}")
    os.rmdir(path)


@click.command('clean')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.option('--verbose', '-v', default=False, is_flag=True,
              help='True if you want to see details of file processing')
@click.argument('path', required=True, nargs=1, type=click.Path())
def _clean(debug, verbose, path):
    """Remove empty folders
    Usage: clean [--verbose|--debug] directory [removeRoot]"""

    logger = log.get_logger(verbose, debug)

    remove_empty_folders(path, logger)



@click.command('generate-db')
@click.option('--path', type=click.Path(file_okay=False),
              required=True, help='Path of your photo library.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _generate_db(path, debug):
    """Regenerate the hash.json database which contains all of the sha256 signatures of media files.
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

    logger = log.get_logger(verbose, debug)

    # Initialize Db
    db = Db(path)


    filesystem = FileSystem(mode='move', dry_run=dry_run, logger=logger)

    if revert_compare:
        summary, has_errors = filesystem.revert_compare(path, db, dry_run)
    else:
        summary, has_errors = filesystem.sort_similar_images(path, db,
                similarity)

    if verbose or debug:
        summary.write()

    if has_errors:
        sys.exit(1)


@click.group()
def main():
    pass


main.add_command(_clean)
main.add_command(_compare)
main.add_command(_sort)
main.add_command(_generate_db)
main.add_command(_verify)
main.add_command(_batch)


if __name__ == '__main__':
    main()
