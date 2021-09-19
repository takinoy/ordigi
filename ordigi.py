#!/usr/bin/env python

import os
import re
import sys

import click

from ordigi.config import Config
from ordigi import constants
from ordigi import log
from ordigi.collection import Collection
from ordigi.geolocation import GeoLocation
from ordigi.media import Media, get_all_subclasses
from ordigi.summary import Summary


_logger_options = [
    click.option('--debug', default=False, is_flag=True,
                  help='Override the value in constants.py with True.'),
    click.option('--verbose', '-v', default=False, is_flag=True,
                  help='True if you want to see details of file processing')
]

_dry_run_options = [
    click.option('--dry-run', default=False, is_flag=True,
              help='Dry run only, no change made to the filesystem.')
]

_filter_option = [
    click.option('--exclude', '-e', default=set(), multiple=True,
                  help='Directories or files to exclude.'),
    click.option('--filter-by-ext', '-f', default=set(), multiple=True,
    help="""Use filename
            extension to filter files for sorting. If value is '*', use
            common media file extension for filtering. Ignored files remain in
            the same directory structure""" ),
    click.option('--glob', '-g', default='**/*',
                  help='Glob file selection')
]


def print_help(command):
    click.echo(command.get_help(click.Context(sort)))


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


def _get_exclude(opt, exclude):
    # if no exclude list was passed in we check if there's a config
    if len(exclude) == 0:
        exclude = opt['exclude']
    return set(exclude)


@click.command('sort')
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_option)
@click.option('--album-from-folder', default=False, is_flag=True,
              help="Use images' folders as their album names.")
@click.option('--destination', '-d', type=click.Path(file_okay=False),
              default=None, help='Sort files into this directory.')
@click.option('--clean', '-C', default=False, is_flag=True,
              help='Clean empty folders')
@click.option('--copy', '-c', default=False, is_flag=True,
              help='True if you want files to be copied over from src_dir to\
              dest_dir rather than moved')
@click.option('--ignore-tags', '-I', default=set(), multiple=True,
              help='Specific tags or group that will be ignored when\
              searching for file data. Example \'File:FileModifyDate\' or \'Filename\'' )
@click.option('--interactive', '-i', default=False, is_flag=True,
              help="Interactive mode")
@click.option('--max-deep', '-m', default=None,
              help='Maximum level to proceed. Number from 0 to desired level.')
@click.option('--remove-duplicates', '-R', default=False, is_flag=True,
              help='True to remove files that are exactly the same in name\
                      and a file hash')
@click.option('--reset-cache', '-r', default=False, is_flag=True,
              help='Regenerate the hash.json and location.json database ')
@click.argument('paths', required=True, nargs=-1, type=click.Path())
def sort(**kwargs):
    """Sort files or directories by reading their EXIF and organizing them
    according to ordigi.conf preferences.
    """

    debug = kwargs['debug']
    destination = kwargs['destination']
    verbose = kwargs['verbose']

    paths = kwargs['paths']

    if kwargs['copy']:
        mode = 'copy'
    else:
        mode = 'move'

    logger = log.get_logger(verbose, debug)

    max_deep = kwargs['max_deep']
    if max_deep is not None:
        max_deep = int(max_deep)

    cache = True
    if kwargs['reset_cache']:
        cache = False

    if len(paths) > 1:
        if not destination:
            # Use last path argument as destination
            destination = paths[-1]
            paths = paths[0:-1]
    elif paths:
        # Source and destination are the same
        destination = paths[0]
    else:
        logger.error(f'`ordigi sort` need at least one path argument')
        sys.exit(1)

    paths = set(paths)

    config = Config(constants.CONFIG_FILE)
    opt = config.get_options()

    exclude = _get_exclude(opt, kwargs['exclude'])
    filter_by_ext = set(kwargs['filter_by_ext'])

    collection = Collection(destination, opt['path_format'],
            kwargs['album_from_folder'], cache, opt['day_begins'], kwargs['dry_run'],
            exclude, filter_by_ext, kwargs['glob'], kwargs['interactive'],
            logger, max_deep, mode)

    loc = GeoLocation(opt['geocoder'], opt['prefer_english_names'],
            opt['timeout'])

    summary, has_errors = collection.sort_files(paths, loc,
            kwargs['remove_duplicates'], kwargs['ignore_tags'])

    if kwargs['clean']:
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
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_option)
@click.option('--dedup-regex', '-d', default=set(), multiple=True,
              help='Regex to match duplicate strings parts')
@click.option('--folders', '-f', default=False, is_flag=True,
              help='Remove empty folders')
@click.option('--max-deep', '-m', default=None,
              help='Maximum level to proceed. Number from 0 to desired level.')
@click.option('--path-string', '-p', default=False, is_flag=True,
              help='Deduplicate path string')
@click.option('--remove-duplicates', '-R', default=False, is_flag=True,
              help='True to remove files that are exactly the same in name\
                      and a file hash')
@click.option('--root', '-r', type=click.Path(file_okay=False),
              default=None, help='Root dir of media collection. If not set, use path')
@click.argument('path', required=True, nargs=1, type=click.Path())
def clean(**kwargs):
    """Remove empty folders
    Usage: clean [--verbose|--debug] directory [removeRoot]"""

    debug = kwargs['debug']
    dry_run = kwargs['dry_run']
    folders = kwargs['folders']
    root = kwargs['root']
    verbose = kwargs['verbose']

    path = kwargs['path']

    logger = log.get_logger(verbose, debug)
    clean_all = False
    if not folders:
        clean_all = True
    if not root:
        root = path

    config = Config(constants.CONFIG_FILE)
    opt = config.get_options()

    exclude = _get_exclude(opt, kwargs['exclude'])
    filter_by_ext = set(kwargs['filter_by_ext'])

    if kwargs['path_string']:
        collection = Collection(root, opt['path_format'], dry_run=dry_run,
                exclude=exclude, filter_by_ext=filter_by_ext, glob=kwargs['glob'],
                logger=logger, max_deep=kwargs['max_deep'], mode='move')
        dedup_regex = list(kwargs['dedup_regex'])
        summary, has_errors = collection.dedup_regex(path, dedup_regex, logger, kwargs['remove_duplicates'])

    if clean_all or folders:
        remove_empty_folders(path, logger)

    if verbose or debug:
        summary.write()

    if has_errors:
        sys.exit(1)


@click.command('generate-db')
@add_options(_logger_options)
@click.option('--path', type=click.Path(file_okay=False),
              required=True, help='Path of your photo library.')
def generate_db(**kwargs):
    """Regenerate the hash.json database which contains all of the sha256 signatures of media files.
    """
    # TODO
    pass


@click.command('verify')
@add_options(_logger_options)
@click.option('--path', type=click.Path(file_okay=False),
              required=True, help='Path of your photo library.')
def verify(**kwargs):
    """Verify hashes"""
    # TODO
    pass


@click.command('compare')
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_option)
@click.option('--find-duplicates', '-f', default=False, is_flag=True)
@click.option('--output-dir', '-o', default=False, is_flag=True, help='output\
        dir')
@click.option('--remove-duplicates', '-r', default=False, is_flag=True)
@click.option('--revert-compare', '-R', default=False, is_flag=True, help='Revert\
        compare')
@click.option('--root', '-r', type=click.Path(file_okay=False),
              default=None, help='Root dir of media collection. If not set, use path')
@click.option('--similar-to', '-s', default=False, help='Similar to given\
        image')
@click.option('--similarity', '-S', default=80, help='Similarity level for\
        images')
@click.argument('path', nargs=1, required=True)
def compare(**kwargs):
    '''Compare files in directories'''

    debug = kwargs['debug']
    dry_run = kwargs['dry_run']
    root = kwargs['root']
    verbose = kwargs['verbose']

    path = kwargs['path']

    logger = log.get_logger(verbose, debug)
    if not root:
        root = kwargs['path']

    config = Config(constants.CONFIG_FILE)
    opt = config.get_options()

    exclude = _get_exclude(opt, kwargs['exclude'])
    filter_by_ext = set(kwargs['filter_by_ext'])

    collection = Collection(root, None, exclude=exclude,
            filter_by_ext=filter_by_ext, glob=kwargs['glob'],
            mode='move', dry_run=dry_run, logger=logger)

    if kwargs['revert_compare']:
        summary, has_errors = collection.revertcompare(path, dry_run)
    else:
        summary, has_errors = collection.sort_similar_images(path, kwargs['similarity'])

    if verbose or debug:
        summary.write()

    if has_errors:
        sys.exit(1)


@click.group()
def main(**kwargs):
    pass


main.add_command(clean)
main.add_command(compare)
main.add_command(sort)
main.add_command(generate_db)
main.add_command(verify)


if __name__ == '__main__':
    main()

