import pytest

CONTENT = "content"

class TestDozo:
    @pytest.mark.skip()
    def test__sort(self):
        assert 0

def test_needsfiles(tmpdir):
    assert tmpdir

def test_create_file(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "hello.txt"
    p.write_text(CONTENT)
    assert p.read_text() == CONTENT
    assert len(list(tmp_path.iterdir())) == 1
