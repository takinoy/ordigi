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


_logger_options = [
    click.option(
        '--debug',
        default=False,
        is_flag=True,
        help='Override the value in constants.py with True.',
    ),
    click.option(
        '--verbose',
        '-v',
        default=False,
        is_flag=True,
        help='True if you want to see details of file processing',
    ),
]

_dry_run_options = [
    click.option(
        '--dry-run',
        default=False,
        is_flag=True,
        help='Dry run only, no change made to the filesystem.',
    )
]

_filter_option = [
    click.option(
        '--exclude',
        '-e',
        default=set(),
        multiple=True,
        help='Directories or files to exclude.',
    ),
    click.option(
        '--filter-by-ext',
        '-f',
        default=set(),
        multiple=True,
        help="""Use filename
            extension to filter files for sorting. If value is '*', use
            common media file extension for filtering. Ignored files remain in
            the same directory structure""",
    ),
    click.option('--glob', '-g', default='**/*', help='Glob file selection'),
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

def get_collection_config(root):
    return Config(os.path.join(root, '.ordigi', 'ordigi.conf'))

@click.command('sort')
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_option)
@click.option(
    '--album-from-folder',
    default=False,
    is_flag=True,
    help="Use images' folders as their album names.",
)
@click.option(
    '--destination',
    '-d',
    type=click.Path(file_okay=False),
    default=None,
    help='Sort files into this directory.',
)
@click.option('--clean', '-C', default=False, is_flag=True, help='Clean empty folders')
@click.option(
    '--copy',
    '-c',
    default=False,
    is_flag=True,
    help='True if you want files to be copied over from src_dir to\
              dest_dir rather than moved',
)
@click.option(
    '--ignore-tags',
    '-I',
    default=set(),
    multiple=True,
    help='Specific tags or group that will be ignored when\
              searching for file data. Example \'File:FileModifyDate\' or \'Filename\'',
)
@click.option(
    '--interactive', '-i', default=False, is_flag=True, help="Interactive mode"
)
@click.option(
    '--path-format',
    '-p',
    default=None,
    help='set custom featured path format',
)
@click.option(
    '--remove-duplicates',
    '-R',
    default=False,
    is_flag=True,
    help='True to remove files that are exactly the same in name\
                      and a file hash',
)
@click.option(
    '--reset-cache',
    '-r',
    default=False,
    is_flag=True,
    help='Regenerate the hash.json and location.json database ',
)
@click.option(
    '--use-date-filename',
    '-f',
    default=False,
    is_flag=True,
    help="Use filename date for media original date.",
)
@click.option(
    '--use-file-dates',
    '-F',
    default=False,
    is_flag=True,
    help="Use file date created or modified for media original date.",
)
@click.argument('paths', required=True, nargs=-1, type=click.Path())
def sort(**kwargs):
    """Sort files or directories by reading their EXIF and organizing them
    according to ordigi.conf preferences.
    """

    root = kwargs['destination']
    log_level = log.level(kwargs['verbose'], kwargs['debug'])

    paths = kwargs['paths']

    if kwargs['copy']:
        mode = 'copy'
    else:
        mode = 'move'

    logger = log.get_logger(level=log_level)

    cache = True
    if kwargs['reset_cache']:
        cache = False

    if len(paths) > 1:
        if not root:
            # Use last path argument as destination
            root = paths[-1]
            paths = paths[0:-1]
    elif paths:
        # Source and destination are the same
        root = paths[0]
    else:
        logger.error(f'`ordigi sort` need at least one path argument')
        sys.exit(1)

    paths = set(paths)

    config = get_collection_config(root)
    opt = config.get_options()

    path_format = opt['path_format']
    if kwargs['path_format']:
        path_format = kwargs['path_format']

    exclude = _get_exclude(opt, kwargs['exclude'])
    filter_by_ext = set(kwargs['filter_by_ext'])

    collection = Collection(
        root,
        kwargs['album_from_folder'],
        cache,
        opt['day_begins'],
        kwargs['dry_run'],
        exclude,
        filter_by_ext,
        kwargs['glob'],
        kwargs['interactive'],
        logger,
        opt['max_deep'],
        mode,
        kwargs['use_date_filename'],
        kwargs['use_file_dates'],
    )

    loc = GeoLocation(opt['geocoder'], logger, opt['prefer_english_names'], opt['timeout'])

    summary, result = collection.sort_files(
        paths, loc, kwargs['remove_duplicates'], kwargs['ignore_tags']
    )

    if kwargs['clean']:
        collection.remove_empty_folders(root)

    if log_level < 30:
        summary.print()

    if not result:
        sys.exit(1)


@click.command('clean')
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_option)
@click.option(
    '--dedup-regex',
    '-d',
    default=set(),
    multiple=True,
    help='Regex to match duplicate strings parts',
)
@click.option(
    '--delete-excluded', '-d', default=False, is_flag=True, help='Remove excluded files'
)
@click.option(
    '--folders', '-f', default=False, is_flag=True, help='Remove empty folders'
)
@click.option(
    '--path-string', '-p', default=False, is_flag=True, help='Deduplicate path string'
)
@click.option(
    '--remove-duplicates',
    '-R',
    default=False,
    is_flag=True,
    help='True to remove files that are exactly the same in name and a file hash',
)
@click.option(
    '--root',
    '-r',
    type=click.Path(file_okay=False),
    default=None,
    help='Root dir of media collection. If not set, use path',
)
@click.argument('path', required=True, nargs=1, type=click.Path())
def clean(**kwargs):
    """Remove empty folders
    Usage: clean [--verbose|--debug] directory [removeRoot]"""

    result = True
    dry_run = kwargs['dry_run']
    folders = kwargs['folders']
    log_level = log.level(kwargs['verbose'], kwargs['debug'])
    root = kwargs['root']

    path = kwargs['path']

    logger = log.get_logger(level=log_level)
    clean_all = False
    if not folders:
        clean_all = True
    if not root:
        root = path

    config = get_collection_config(root)
    opt = config.get_options()

    exclude = _get_exclude(opt, kwargs['exclude'])
    filter_by_ext = set(kwargs['filter_by_ext'])

    collection = Collection(
        root,
        dry_run=dry_run,
        exclude=exclude,
        filter_by_ext=filter_by_ext,
        glob=kwargs['glob'],
        logger=logger,
        max_deep=opt['max_deep'],
    )

    if kwargs['path_string']:
        dedup_regex = list(kwargs['dedup_regex'])
        summary, result = collection.dedup_regex(
            path, dedup_regex, kwargs['remove_duplicates']
        )

    if clean_all or folders:
        summary = collection.remove_empty_folders(path)

    if kwargs['delete_excluded']:
        summary = collection.remove_excluded_files()

    if log_level < 30:
        summary.print()

    if not result:
        sys.exit(1)


@click.command('init')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def init(**kwargs):
    """Regenerate the hash.json database which contains all of the sha256 signatures of media files."""
    root = kwargs['path']
    config = get_collection_config(root)
    opt = config.get_options()
    log_level = log.level(kwargs['verbose'], kwargs['debug'])

    logger = log.get_logger(level=log_level)
    loc = GeoLocation(opt['geocoder'], logger, opt['prefer_english_names'], opt['timeout'])
    collection = Collection(root, exclude=opt['exclude'], logger=logger)
    summary = collection.init(loc)

    if log_level < 30:
        summary.print()


@click.command('update')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def update(**kwargs):
    """Regenerate the hash.json database which contains all of the sha256 signatures of media files."""
    root = kwargs['path']
    config = get_collection_config(root)
    opt = config.get_options()
    log_level = log.level(kwargs['verbose'], kwargs['debug'])

    logger = log.get_logger(level=log_level)
    loc = GeoLocation(opt['geocoder'], logger, opt['prefer_english_names'], opt['timeout'])
    collection = Collection(root, exclude=opt['exclude'], logger=logger)
    summary = collection.update(loc)

    if log_level < 30:
        summary.print()


@click.command('check')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def check(**kwargs):
    """check db and verify hashes"""
    log_level = log.level(kwargs['verbose'], kwargs['debug'])
    logger = log.get_logger(level=log_level)
    root = kwargs['path']
    config = get_collection_config(root)
    opt = config.get_options()
    collection = Collection(root, exclude=opt['exclude'], logger=logger)
    result = collection.check_db()
    if result:
        summary, result = collection.check_files()
        if log_level < 30:
            summary.print()
        if not result:
            sys.exit(1)
    else:
        logger.error('Db data is not accurate run `ordigi update`')
        sys.exit(1)


@click.command('compare')
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_option)
@click.option('--find-duplicates', '-f', default=False, is_flag=True)
@click.option(
    '--output-dir',
    '-o',
    default=False,
    is_flag=True,
    help='output dir',
)
@click.option('--remove-duplicates', '-r', default=False, is_flag=True)
@click.option(
    '--revert-compare',
    '-R',
    default=False,
    is_flag=True,
    help='Revert compare',
)
@click.option(
    '--root',
    '-r',
    type=click.Path(file_okay=False),
    default=None,
    help='Root dir of media collection. If not set, use path',
)
@click.option(
    '--similar-to',
    '-s',
    default=False,
    help='Similar to given image',
)
@click.option(
    '--similarity',
    '-S',
    default=80,
    help='Similarity level for images',
)
@click.argument('path', nargs=1, required=True)
def compare(**kwargs):
    '''Compare files in directories'''

    dry_run = kwargs['dry_run']
    log_level = log.level(kwargs['verbose'], kwargs['debug'])
    root = kwargs['root']

    path = kwargs['path']

    logger = log.get_logger(level=log_level)
    if not root:
        root = kwargs['path']

    config = get_collection_config(root)
    opt = config.get_options()

    exclude = _get_exclude(opt, kwargs['exclude'])
    filter_by_ext = set(kwargs['filter_by_ext'])

    collection = Collection(
        root,
        exclude=exclude,
        filter_by_ext=filter_by_ext,
        glob=kwargs['glob'],
        dry_run=dry_run,
        logger=logger,
    )

    if kwargs['revert_compare']:
        summary, result = collection.revert_compare(path)
    else:
        summary, result = collection.sort_similar_images(path, kwargs['similarity'])

    if log_level < 30:
        summary.print()

    if not result:
        sys.exit(1)


@click.group()
def main(**kwargs):
    pass


main.add_command(clean)
main.add_command(check)
main.add_command(compare)
main.add_command(init)
main.add_command(sort)
main.add_command(update)


if __name__ == '__main__':
    main()
