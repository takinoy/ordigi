import shutil
from click.testing import CliRunner
from pathlib import Path
import pytest
import inquirer

from ordigi import cli
from ordigi.request import Input

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
        cls.logger_options = ('--debug', '--log')
        cls.filter_options = (
            ('--ignore-tags', 'CreateDate'),
            ('--ext', 'jpg'),
            ('--glob', '*'),
        )
        cls.sort_options = (
            '--album-from-folder',
            '--fill-date-original',
            '--path-format',
            '--remove-duplicates',
            '--use-date-filename',
            '--use-file-dates',
        )

    def assert_cli(self, command, attributes, state=0):
        result = self.runner.invoke(command, [*attributes])
        assert result.exit_code == state, (command, attributes)

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

    def test_commands(self, tmp_path):
        # Check if fail if path not exist
        commands = [
            cli._check,
            cli._clean,
            cli._compare,
            cli._edit,
            cli._import,
            cli._sort,
            cli._update,
        ]

        not_exist = tmp_path.joinpath('not_exist')

        for command in commands:
            if command.name == 'edit':
                self.assert_cli(command, ['-k', 'date_original', not_exist], state=1)
            else:
                self.assert_cli(command, [not_exist], state=1)

        self.assert_cli(cli._clone, [str(not_exist)], state=2)
        self.assert_cli(cli._init, [str(not_exist)], state=0)

    def test_edit(self, monkeypatch):

        bool_options = (
            *self.logger_options,
        )

        arg_options = (
            *self.filter_options,
        )

        def mockreturn(self, message):
            return '03-12-2021 08:12:35'

        monkeypatch.setattr(Input, 'text', mockreturn)

        args = (
            '--key',
            'date_original',
            '--overwrite',
            str(self.src_path.joinpath('test_exif/photo.png')),
            str(self.src_path),
        )

        self.assert_cli(cli._init, [str(self.src_path)])
        self.assert_cli(cli._edit, args)

        # self.assert_options(cli._edit, bool_options, arg_options, args)
        # self.assert_all_options(cli._edit, bool_options, arg_options, args)

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

        self.assert_cli(cli._init, paths)
        self.assert_cli(cli._sort, paths)

        self.assert_options(cli._sort, bool_options, arg_options, paths)
        self.assert_all_options(cli._sort, bool_options, arg_options, paths)

    def test_clone(self, tmp_path):

        paths = (str(self.src_path), str(tmp_path))

        self.assert_cli(cli._init, [str(self.src_path)])
        self.assert_cli(cli._clone, ['--log', *paths])

    def assert_init(self, tmp_path, conf_path):
        bool_options = (
            *self.logger_options,
            '--user-config',
        )
        arg_options = (
            ('--config', conf_path),
        )

        paths = (str(self.src_path),)
        self.assert_options(cli._init, bool_options, arg_options, paths)
        path = (str(tmp_path.joinpath('test')),)
        self.assert_options(cli._init, bool_options, arg_options, path)

    def assert_update(self):
        bool_options = (
            *self.logger_options,
            '--checksum',
        )
        arg_options = ()

        file_path = Path(ORDIGI_PATH, 'samples/test_exif/photo.cr2')
        dest_path = self.src_path / 'photo_moved.cr2'
        src_path = (str(self.src_path),)
        shutil.copyfile(file_path, dest_path)
        self.assert_options(cli._update, bool_options, arg_options, src_path)

    def assert_check(self):
        bool_options = (*self.logger_options,)
        arg_options = ()

        paths = (str(self.src_path),)
        self.assert_options(cli._check, bool_options, arg_options, paths)

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

    def test_init_update_check_clean(self, tmp_path, conf_path):
        self.assert_init(tmp_path, conf_path)
        self.assert_update()
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
            ('--exclude', '.DS_Store'),
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

        # Workaround
        self.assert_cli(cli._update, paths)

        self.assert_cli(cli._compare, paths)
        self.assert_options(cli._compare, bool_options, arg_options, paths)

    def test_check(self):
        self.assert_cli(cli._init, (str(self.src_path),))
        self.assert_check()


def test_needsfiles(tmpdir):
    assert tmpdir


def test_create_file(tmp_path):
    directory = tmp_path / "sub"
    directory.mkdir()
    path = directory / "hello.txt"
    path.write_text(CONTENT)
    assert path.read_text() == CONTENT
    assert len(list(tmp_path.iterdir())) == 1
