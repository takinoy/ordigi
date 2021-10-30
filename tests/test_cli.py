from imp import load_source
from pathlib import Path
from click.testing import CliRunner
import pytest
import sys

CONTENT = "content"

import ipdb; ipdb.set_trace()
ordigi = load_source('cli', str(Path(__file__).parent.parent) + 'cli.py')

class TestOrdigi:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.runner = CliRunner()
        cls.src_path, cls.file_paths = sample_files_paths

    def test__sort(self):
        import ipdb; ipdb.set_trace()
        result = self.runner.invoke(cli._sort, [str(self.src_path)])


def test_needsfiles(tmpdir):
    assert tmpdir


def test_create_file(tmp_path):
    directory = tmp_path / "sub"
    directory.mkdir()
    path = directory / "hello.txt"
    path.write_text(CONTENT)
    assert path.read_text() == CONTENT
    assert len(list(tmp_path.iterdir())) == 1
