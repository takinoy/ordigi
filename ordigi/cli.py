#!/usr/bin/env python

import os
from pathlib import Path
import re
import sys

import click

from ordigi import LOG
from ordigi.config import Config
from ordigi import log
from ordigi.collection import Collection
from ordigi.geolocation import GeoLocation

_logger_options = [
    click.option(
        '--verbose',
        '-v',
        default='WARNING',
        help='True if you want to see details of file processing',
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
    )
]

_filter_options = [
    click.option(
        '--exclude',
        '-E',
        default=None,
        multiple=True,
        help='Directories or files to exclude.',
    ),
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
        default=False,
        is_flag=True,
        help="Use images' folders as their album names.",
    ),
    click.option(
        '--path-format',
        '-p',
        default=None,
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


def _get_exclude(opt, exclude):
    # if no exclude list was passed in we check if there's a config
    if len(exclude) == 0:
        exclude = opt['exclude']
    return set(exclude)


def get_collection_config(root):
    return Config(root.joinpath('.ordigi', 'ordigi.conf'))



def _get_paths(paths, root):
    root = Path(root).expanduser().absolute()
    if not paths:
        paths = {root}
    else:
        paths = set()
        for path in paths:
            paths.add(Path(path).expanduser().absolute())

    return paths, root


@click.command('import')
@add_options(_logger_options)
@add_options(_input_options)
@add_options(_dry_run_options)
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
    LOG = log.get_logger(level=log_level)

    root = kwargs['dest']
    src_paths = kwargs['src']
    src_paths, root = _get_paths(src_paths, root)

    if kwargs['copy']:
        import_mode = 'copy'
    else:
        import_mode = 'move'

    config = get_collection_config(root)
    opt = config.get_options()

    path_format = opt['path_format']
    if kwargs['path_format']:
        path_format = kwargs['path_format']

    exclude = _get_exclude(opt, kwargs['exclude'])
    extensions = set(kwargs['ext'])

    collection = Collection(
        root,
        kwargs['album_from_folder'],
        False,
        opt['day_begins'],
        kwargs['dry_run'],
        exclude,
        extensions,
        kwargs['glob'],
        kwargs['interactive'],
        kwargs['ignore_tags'],
        opt['max_deep'],
        kwargs['use_date_filename'],
        kwargs['use_file_dates'],
    )

    loc = GeoLocation(opt['geocoder'], opt['prefer_english_names'], opt['timeout'])

    summary = collection.sort_files(
        src_paths, path_format, loc, import_mode, kwargs['remove_duplicates']
    )

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)

@click.command('sort')
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
    LOG = log.get_logger(level=log_level)

    subdirs = kwargs['subdirs']
    root = kwargs['dest']
    paths, root = _get_paths(subdirs, root)

    cache = True
    if kwargs['reset_cache']:
        cache = False

    config = get_collection_config(root)
    opt = config.get_options()

    path_format = opt['path_format']
    if kwargs['path_format']:
        path_format = kwargs['path_format']

    exclude = _get_exclude(opt, kwargs['exclude'])
    extensions = set(kwargs['ext'])

    collection = Collection(
        root,
        kwargs['album_from_folder'],
        cache,
        opt['day_begins'],
        kwargs['dry_run'],
        exclude,
        extensions,
        kwargs['glob'],
        kwargs['interactive'],
        kwargs['ignore_tags'],
        opt['max_deep'],
        kwargs['use_date_filename'],
        kwargs['use_file_dates'],
    )

    loc = GeoLocation(opt['geocoder'], opt['prefer_english_names'], opt['timeout'])

    summary = collection.sort_files(
        paths, path_format, loc, kwargs['remove_duplicates']
    )

    if kwargs['clean']:
        collection.remove_empty_folders(root)

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@click.command('clean')
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
    """Remove empty folders"""

    dry_run = kwargs['dry_run']
    folders = kwargs['folders']
    log_level = log.get_level(kwargs['verbose'])
    LOG = log.get_logger(level=log_level)

    subdirs = kwargs['subdirs']
    root = kwargs['collection']
    paths, root = _get_paths(subdirs, root)

    clean_all = False
    if not folders:
        clean_all = True

    config = get_collection_config(root)
    opt = config.get_options()

    exclude = _get_exclude(opt, kwargs['exclude'])
    extensions = set(kwargs['ext'])

    collection = Collection(
        root,
        dry_run=dry_run,
        exclude=exclude,
        extensions=extensions,
        glob=kwargs['glob'],
        max_deep=opt['max_deep'],
    )

    if kwargs['path_string']:
        dedup_regex = set(kwargs['dedup_regex'])
        collection.dedup_path(
            paths, dedup_regex, kwargs['remove_duplicates']
        )

    for path in paths:
        if clean_all or folders:
            collection.remove_empty_folders(path)

        if kwargs['delete_excluded']:
            collection.remove_excluded_files()

    summary = collection.summary

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@click.command('init')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def _init(**kwargs):
    """
    Init media collection database.
    """
    root = Path(kwargs['path']).expanduser().absolute()
    config = get_collection_config(root)
    opt = config.get_options()
    log_level = log.get_level(kwargs['verbose'])
    LOG = log.get_logger(level=log_level)

    loc = GeoLocation(opt['geocoder'], opt['prefer_english_names'], opt['timeout'])
    collection = Collection(root, exclude=opt['exclude'])
    summary = collection.init(loc)

    if log_level < 30:
        summary.print()


@click.command('update')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def _update(**kwargs):
    """
    Update media collection database.
    """
    root = Path(kwargs['path']).expanduser().absolute()
    config = get_collection_config(root)
    opt = config.get_options()
    log_level = log.get_level(kwargs['verbose'])
    LOG = log.get_logger(level=log_level)

    loc = GeoLocation(opt['geocoder'], opt['prefer_english_names'], opt['timeout'])
    collection = Collection(root, exclude=opt['exclude'])
    summary = collection.update(loc)

    if log_level < 30:
        summary.print()


@click.command('check')
@add_options(_logger_options)
@click.argument('path', required=True, nargs=1, type=click.Path())
def _check(**kwargs):
    """
    Check media collection.
    """
    root = Path(kwargs['path']).expanduser().absolute()

    log_level = log.get_level(kwargs['verbose'])
    LOG = log.get_logger(level=log_level)
    config = get_collection_config(root)
    opt = config.get_options()
    collection = Collection(root, exclude=opt['exclude'])
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


@click.command('compare')
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

    dry_run = kwargs['dry_run']
    subdirs = kwargs['subdirs']
    root = kwargs['collection']

    log_level = log.get_level(kwargs['verbose'])
    LOG = log.get_logger(level=log_level)
    paths, root = _get_paths(subdirs, root)

    config = get_collection_config(root)
    opt = config.get_options()

    exclude = _get_exclude(opt, kwargs['exclude'])
    extensions = set(kwargs['ext'])

    collection = Collection(
        root,
        exclude=exclude,
        extensions=extensions,
        glob=kwargs['glob'],
        dry_run=dry_run,
    )

    for path in paths:
        collection.sort_similar_images(path, kwargs['similarity'])

    summary = collection.summary

    if log_level < 30:
        summary.print()

    if summary.errors:
        sys.exit(1)


@click.group()
def main(**kwargs):
    pass


main.add_command(_clean)
main.add_command(_check)
main.add_command(_compare)
main.add_command(_init)
main.add_command(_import)
main.add_command(_sort)
main.add_command(_update)
