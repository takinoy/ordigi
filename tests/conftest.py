""" pytest test configuration """

import pytest

from dozo.exiftool import _ExifToolProc


@pytest.fixture(autouse=True)
def reset_singletons():
    """ Need to clean up any ExifTool singletons between tests """
    _ExifToolProc.instance = None


