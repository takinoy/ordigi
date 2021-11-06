import shutil
from click.testing import CliRunner
from pathlib import Path
import pytest

from ordigi import cli

CONTENT = "content"

ORDIGI_PATH = Path(__file__).parent.parent


def get_arg_options_list(arg_options):
    arg_options_list = []
    for opt, arg in arg_options:
        arg_options_list.append(opt)
        arg_options_list.append(arg)

    return arg_options_list


class TestOrdigi:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.runner = CliRunner()
        cls.src_path, cls.file_paths = sample_files_paths
        cls.logger_options = (
            '--debug',
            '--verbose',
        )
        cls.filter_options = (
            ('--exclude', '.DS_Store'),
            ('--ignore-tags', 'CreateDate'),
            ('--ext', 'jpg'),
            ('--glob', '*'),
        )
        cls.sort_options = (
            '--album-from-folder',
            '--path-format',
            '--remove-duplicates',
            '--use-date-filename',
            '--use-file-dates',
        )

    def assert_cli(self, command, paths):
        result = self.runner.invoke(command, [*paths])
        assert result.exit_code == 0

    def assert_options(self, command, bool_options, arg_options, paths):
        for bool_option in bool_options:
            self.assert_cli(command, [bool_option, *paths])

        for opt, arg in arg_options:
            self.assert_cli(command, [opt, arg, *paths])

    def assert_all_options(self, command, bool_options, arg_options, paths):
        arg_options_list = get_arg_options_list(arg_options)
        self.assert_cli(command, [
            *bool_options, *arg_options_list, *paths,
        ])

    def test_sort(self):
        bool_options = (
            *self.logger_options,
            # '--interactive',
            '--dry-run',
            '--album-from-folder',
            '--remove-duplicates',
            '--use-date-filename',
            '--use-file-dates',
            '--clean',
        )

        arg_options = (
            *self.filter_options,
            ('--path-format', '{%Y}/{folder}/{name}.{ext}'),

        )

        paths = (str(self.src_path),)

        self.assert_cli(cli._sort, paths)

        self.assert_options(cli._sort, bool_options, arg_options, paths)
        self.assert_all_options(cli._sort, bool_options, arg_options, paths)

    def assert_init(self):
        for bool_option in self.logger_options:
            result = self.runner.invoke(
                    cli._init, [bool_option, str(self.src_path
            )])
            assert result.exit_code == 0, bool_option

    def assert_update(self):
        file_path = Path(ORDIGI_PATH, 'samples/test_exif/photo.cr2')
        dest_path = self.src_path / 'photo_moved.cr2'
        shutil.copyfile(file_path, dest_path)
        for bool_option in self.logger_options:
            result = self.runner.invoke(
                    cli._update, [bool_option, str(self.src_path
            )])
            assert result.exit_code == 0, bool_option

    def assert_check(self):
        for bool_option in self.logger_options:
            result = self.runner.invoke(
                    cli._check, [bool_option, str(self.src_path
            )])
            assert result.exit_code == 0, bool_option

    def assert_clean(self):
        bool_options = (
            *self.logger_options,
            # '--interactive',
            '--dry-run',
            '--delete-excluded',
            '--folders',
            '--path-string',
            '--remove-duplicates',
        )

        arg_options = (
            *self.filter_options,
            ('--dedup-regex', r'\d{4}-\d{2}'),
        )

        paths = ('test_exif', str(self.src_path))
        self.assert_cli(cli._clean, paths)

        paths = (str(self.src_path),)
        self.assert_cli(cli._clean, paths)

        self.assert_options(cli._clean, bool_options, arg_options, paths)
        self.assert_all_options(cli._clean, bool_options, arg_options, paths)

    def test_init_update_check_clean(self):
        self.assert_init()
        self.assert_update()
        self.assert_check()
        self.assert_clean()

    def test_import(self, tmp_path):
        bool_options = (
            *self.logger_options,
            # '--interactive',
            '--dry-run',
            '--album-from-folder',
            '--remove-duplicates',
            '--use-date-filename',
            '--use-file-dates',
            '--copy',
        )

        arg_options = (
            *self.filter_options,
            ('--path-format', '{%Y}/{folder}/{stem}.{ext}'),

        )

        paths = (str(self.src_path), str(tmp_path))

        result = self.runner.invoke(cli._import, ['--copy', *paths])
        assert result.exit_code == 0

        self.assert_options(cli._import, bool_options, arg_options, paths)
        self.assert_all_options(cli._import, bool_options, arg_options, paths)

    def test_compare(self):
        bool_options = (
            *self.logger_options,
            # '--interactive',
            '--dry-run',
            '--find-duplicates',
            '--remove-duplicates',
        )

        arg_options = (
            *self.filter_options,
            # ('--similar-to', ''),
            ('--similarity', '65'),
        )

        paths = (str(self.src_path),)

        self.assert_cli(cli._compare, paths)
        self.assert_options(cli._compare, bool_options, arg_options, paths)


def test_needsfiles(tmpdir):
    assert tmpdir


def test_create_file(tmp_path):
    directory = tmp_path / "sub"
    directory.mkdir()
    path = directory / "hello.txt"
    path.write_text(CONTENT)
    assert path.read_text() == CONTENT
    assert len(list(tmp_path.iterdir())) == 1
