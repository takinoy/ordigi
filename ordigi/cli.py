#!/usr/bin/env python

from pathlib import Path
import sys

import click

from ordigi import log, LOG
from ordigi.collection import Collection
from ordigi import constants
from ordigi.geolocation import GeoLocation
from ordigi import utils

_logger_options = [
    click.option(
        '--verbose',
        '-v',
        default='WARNING',
        help='Log level [WARNING,INFO,DEBUG,NOTSET]',
    ),
]

_input_options = [
    click.option(
        '--interactive', '-i', default=False, is_flag=True, help="Interactive mode"
    ),
]

_dry_run_options = [
    click.option(
        '--dry-run',
        default=False,
        is_flag=True,
        help='Dry run only, no change made to the filesystem.',
    ),
]

_exclude_options = [
    click.option(
        '--exclude',
        '-E',
        default=None,
        multiple=True,
        help='Directories or files to exclude.',
    ),
]

_filter_options = [
    click.option(
        '--ext',
        '-e',
        default=None,
        multiple=True,
        help="""Use filename
            extension to filter files for sorting. If value is '*', use
            common media file extension for filtering. Ignored files remain in
            the same directory structure""",
    ),
    click.option(
        '--ignore-tags',
        '-I',
        default=None,
        multiple=True,
        help='Specific tags or group that will be ignored when\
                  searching for file data. Example \'File:FileModifyDate\' or \'Filename\'',
    ),
    click.option('--glob', '-g', default='**/*', help='Glob file selection'),
]


_sort_options = [
    click.option(
        '--album-from-folder',
        '-a',
        default=False,
        is_flag=True,
        help="Use images' folders as their album names.",
    ),
    click.option(
        '--fill-date-original',
        '-O',
        default=False,
        is_flag=True,
        help="Fill date original from date media if not set",
    ),
    click.option(
        '--path-format',
        '-p',
        default=constants.DEFAULT_PATH_FORMAT,
        help='Custom featured path format',
    ),
    click.option(
        '--remove-duplicates',
        '-R',
        default=False,
        is_flag=True,
        help='True to remove files that are exactly the same in name\
                          and a file hash',
    ),
    click.option(
        '--use-date-filename',
        '-f',
        default=False,
        is_flag=True,
        help="Use filename date for media original date.",
    ),
    click.option(
        '--use-file-dates',
        '-F',
        default=False,
        is_flag=True,
        help="Use file date created or modified for media original date.",
    ),
]


def print_help(command):
    click.echo(command.get_help(click.Context(command)))


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


def _get_paths(paths, root):
    root = Path(root).expanduser().absolute()
    if not paths:
        absolute_paths = {root}
    else:
        absolute_paths = set()
        for path in paths:
            absolute_paths.add(Path(path).expanduser().absolute())

    return absolute_paths, root


def _cli_get_location(collection):
    gopt = collection.opt['Geolocation']
    return GeoLocation(
        gopt['geocoder'],
        gopt['prefer_english_names'],
        gopt['timeout'],
    )


def _cli_sort(collection, src_paths, import_mode):
    loc = _cli_get_location(collection)

    return collection.sort_files(src_paths, loc, import_mode)


@click.group()
def cli(**kwargs):
    pass


@cli.command('check')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def _check(**kwargs):
    """
    Check media collection.
    """
    root = Path(kwargs['path']).expanduser().absolute()

    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    collection = Collection(root)
    result = collection.check_db()
    if result:
        summary = collection.check_files()
        if log_level < 30:
            summary.print()
        if summary.errors:
            sys.exit(1)
    else:
        LOG.error('Db data is not accurate run `ordigi update`')
        sys.exit(1)


@cli.command('clean')
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_options)
@click.option(
    '--dedup-regex',
    '-d',
    default=None,
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
@click.argument('subdirs', required=False, nargs=-1, type=click.Path())
@click.argument('collection', required=True, nargs=1, type=click.Path())
def _clean(**kwargs):
    """Clean media collection"""

    folders = kwargs['folders']
    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    subdirs = kwargs['subdirs']
    root = kwargs['collection']
    paths, root = _get_paths(subdirs, root)

    collection = Collection(
        root,
        {
            'dry_run': kwargs['dry_run'],
            'extensions': kwargs['ext'],
            'glob': kwargs['glob'],
            'remove_duplicates': kwargs['remove_duplicates'],
        },
    )

    # os.path.join(
    # TODO make function to remove duplicates
    # path_format = collection.opt['Path']['path_format']
    # summary = collection.sort_files(paths, None)

    if kwargs['path_string']:
        dedup_regex = set(kwargs['dedup_regex'])
        collection.dedup_path(paths, dedup_regex)

    for path in paths:
        if folders:
            collection.remove_empty_folders(path)

        if kwargs['delete_excluded']:
            collection.remove_excluded_files()

    summary = collection.summary

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@cli.command('clone')
@add_options(_logger_options)
@add_options(_dry_run_options)
@click.argument('src', required=True, nargs=1, type=click.Path())
@click.argument('dest', required=True, nargs=1, type=click.Path())
def _clone(**kwargs):
    """Clone media collection to another location"""

    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    src_path = Path(kwargs['src']).expanduser().absolute()
    dest_path = Path(kwargs['dest']).expanduser().absolute()

    dry_run = kwargs['dry_run']

    src_collection = Collection(
        src_path, {'cache': True, 'dry_run': dry_run}
    )

    if dest_path.exists() and not utils.empty_dir(dest_path):
        LOG.error(f'Destination collection path {dest_path} must be empty directory')
        sys.exit(1)

    summary = src_collection.clone(dest_path)

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@cli.command('compare')
@add_options(_logger_options)
@add_options(_dry_run_options)
@add_options(_filter_options)
@click.option('--find-duplicates', '-f', default=False, is_flag=True)
@click.option('--remove-duplicates', '-r', default=False, is_flag=True)
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
@click.argument('subdirs', required=False, nargs=-1, type=click.Path())
@click.argument('collection', required=True, nargs=1, type=click.Path())
def _compare(**kwargs):
    """
    Sort similar images in directories
    """

    subdirs = kwargs['subdirs']
    root = kwargs['collection']

    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)
    paths, root = _get_paths(subdirs, root)

    collection = Collection(
        root,
        {
            'extensions': kwargs['ext'],
            'glob': kwargs['glob'],
            'dry_run': kwargs['dry_run'],
            'remove_duplicates': kwargs['remove_duplicates'],
        },
    )

    for path in paths:
        collection.sort_similar_images(path, kwargs['similarity'])

    summary = collection.summary

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@cli.command('edit')
@add_options(_logger_options)
@add_options(_exclude_options)
@add_options(_filter_options)
@click.option(
    '--key',
    '-k',
    default=None,
    multiple=True,
    help="Select exif tags groups to edit",
)
@click.option(
    '--overwrite',
    '-O',
    default=False,
    is_flag=True,
    help="Overwrite db and exif value by key value",
)
@click.argument('subdirs', required=False, nargs=-1, type=click.Path())
@click.argument('path', required=True, nargs=1, type=click.Path())
def _edit(**kwargs):
    """Edit EXIF metadata in files or directories"""

    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    paths, root = _get_paths(kwargs['subdirs'], kwargs['path'])

    overwrite = kwargs['overwrite']

    collection = Collection(
        root,
        {
            'cache': True,
            'ignore_tags': kwargs['ignore_tags'],
            'exclude': kwargs['exclude'],
            'extensions': kwargs['ext'],
            'glob': kwargs['glob'],
        }
    )

    editable_keys = (
        'album',
        'camera_make',
        'camera_model',
        'city',
        'country',
        # 'date_created',
        'date_media',
        # 'date_modified',
        'date_original',
        'latitude',
        'location',
        'longitude',
        'latitude_ref',
        'longitude_ref',
        'original_name',
        'state',
        'title',
    )

    if not kwargs['key']:
        keys = set(editable_keys)
    else:
        keys = set(kwargs['key'])
        if 'coordinates' in keys:
            keys.remove('coordinates')
            keys.update(['latitude', 'longitude'])

    location = False
    for key in keys:
        if key not in editable_keys:
            LOG.error(f"key '{key}' is not valid")
            sys.exit(1)

        if key in (
            'city',
            'latitude',
            'location',
            'longitude',
            'latitude_ref',
            'longitude_ref',
        ):
            location = True

    if location:
        loc = _cli_get_location(collection)
    else:
        loc = None

    summary = collection.edit_metadata(paths, keys, loc, overwrite)

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@cli.command('init')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def _init(**kwargs):
    """
    Init media collection database.
    """
    root = Path(kwargs['path']).expanduser().absolute()
    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    collection = Collection(root)

    loc = _cli_get_location(collection)

    summary = collection.init(loc)

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@cli.command('import')
@add_options(_logger_options)
@add_options(_input_options)
@add_options(_dry_run_options)
@add_options(_exclude_options)
@add_options(_filter_options)
@add_options(_sort_options)
@click.option(
    '--copy',
    '-c',
    default=False,
    is_flag=True,
    help='True if you want files to be copied over from src_dir to\
              dest_dir rather than moved',
)
@click.argument('src', required=False, nargs=-1, type=click.Path())
@click.argument('dest', required=True, nargs=1, type=click.Path())
def _import(**kwargs):
    """Sort files or directories by reading their EXIF and organizing them
    according to ordigi.conf preferences.
    """
    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    src_paths, root = _get_paths(kwargs['src'], kwargs['dest'])

    collection = Collection(
        root,
        {
            'album_from_folder': kwargs['album_from_folder'],
            'cache': False,
            'ignore_tags': kwargs['ignore_tags'],
            'use_date_filename': kwargs['use_date_filename'],
            'use_file_dates': kwargs['use_file_dates'],
            'exclude': kwargs['exclude'],
            'extensions': kwargs['ext'],
            'glob': kwargs['glob'],
            'dry_run': kwargs['dry_run'],
            'interactive': kwargs['interactive'],
            'path_format': kwargs['path_format'],
            'remove_duplicates': kwargs['remove_duplicates'],
        }
    )

    if kwargs['copy']:
        import_mode = 'copy'
    else:
        import_mode = 'move'
    summary = _cli_sort(collection, src_paths, import_mode)

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@cli.command('sort')
@add_options(_logger_options)
@add_options(_input_options)
@add_options(_dry_run_options)
@add_options(_filter_options)
@add_options(_sort_options)
@click.option('--clean', '-C', default=False, is_flag=True, help='Clean empty folders')
@click.option(
    '--reset-cache',
    '-r',
    default=False,
    is_flag=True,
    help='Regenerate the hash.json and location.json database ',
)
@click.argument('subdirs', required=False, nargs=-1, type=click.Path())
@click.argument('dest', required=True, nargs=1, type=click.Path())
def _sort(**kwargs):
    """Sort files or directories by reading their EXIF and organizing them
    according to ordigi.conf preferences.
    """
    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    paths, root = _get_paths(kwargs['subdirs'], kwargs['dest'])

    cache = not kwargs['reset_cache']

    collection = Collection(
        root,
        {
            'album_from_folder': kwargs['album_from_folder'],
            'cache': cache,
            'fill_date_original': kwargs['fill_date_original'],
            'ignore_tags': kwargs['ignore_tags'],
            'use_date_filename': kwargs['use_date_filename'],
            'use_file_dates': kwargs['use_file_dates'],
            'extensions': kwargs['ext'],
            'glob': kwargs['glob'],
            'dry_run': kwargs['dry_run'],
            'interactive': kwargs['interactive'],
            'remove_duplicates': kwargs['remove_duplicates'],
        }
    )

    summary = _cli_sort(collection, paths, False)

    if kwargs['clean']:
        collection.remove_empty_folders(root)

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@cli.command('update')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def _update(**kwargs):
    """
    Update media collection database.
    """
    root = Path(kwargs['path']).expanduser().absolute()
    log_level = log.get_level(kwargs['verbose'])
    log.console(LOG, level=log_level)

    collection = Collection(root)
    loc = _cli_get_location(collection)
    summary = collection.update(loc)

    if log_level < 30:
        summary.print()


if __name__ == '__main__':
    cli()
