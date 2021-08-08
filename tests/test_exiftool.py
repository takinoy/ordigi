import json
import pytest
import subprocess

import dozo.exiftool
from dozo.exiftool import get_exiftool_path

TEST_FILE_ONE_KEYWORD = "samples/images/wedding.jpg"
TEST_FILE_BAD_IMAGE = "samples/images/badimage.jpeg"
TEST_FILE_WARNING = "samples/images/exiftool_warning.heic"
TEST_FILE_MULTI_KEYWORD = "samples/images/Tulips.jpg"
TEST_MULTI_KEYWORDS = [
    "Top Shot",
    "flowers",
    "flower",
    "design",
    "Stock Photography",
    "vibrant",
    "plastic",
    "Digital Nomad",
    "close up",
    "stock photo",
    "outdoor",
    "wedding",
    "Reiseblogger",
    "fake",
    "colorful",
    "Indoor",
    "display",
    "photography",
]

PHOTOS_DB = "tests/Test-10.15.4.photoslibrary"
EXIF_UUID = {
    "6191423D-8DB8-4D4C-92BE-9BBBA308AAC4": {
        "EXIF:DateTimeOriginal": "2019:07:04 16:24:01",
        "EXIF:LensModel": "XF18-55mmF2.8-4 R LM OIS",
        "IPTC:Keywords": [
            "Digital Nomad",
            "Indoor",
            "Reiseblogger",
            "Stock Photography",
            "Top Shot",
            "close up",
            "colorful",
            "design",
            "display",
            "fake",
            "flower",
            "outdoor",
            "photography",
            "plastic",
            "stock photo",
            "vibrant",
        ],
        "IPTC:DocumentNotes": "https://flickr.com/e/l7FkSm4f2lQkSV3CG6xlv8Sde5uF3gVu4Hf0Qk11AnU%3D",
    },
    "E9BC5C36-7CD1-40A1-A72B-8B8FAC227D51": {
        "EXIF:Make": "NIKON CORPORATION",
        "EXIF:Model": "NIKON D810",
        "IPTC:DateCreated": "2019:04:15",
    },
}
EXIF_UUID_NO_GROUPS = {
    "6191423D-8DB8-4D4C-92BE-9BBBA308AAC4": {
        "DateTimeOriginal": "2019:07:04 16:24:01",
        "LensModel": "XF18-55mmF2.8-4 R LM OIS",
        "Keywords": [
            "Digital Nomad",
            "Indoor",
            "Reiseblogger",
            "Stock Photography",
            "Top Shot",
            "close up",
            "colorful",
            "design",
            "display",
            "fake",
            "flower",
            "outdoor",
            "photography",
            "plastic",
            "stock photo",
            "vibrant",
        ],
        "DocumentNotes": "https://flickr.com/e/l7FkSm4f2lQkSV3CG6xlv8Sde5uF3gVu4Hf0Qk11AnU%3D",
    },
    "E9BC5C36-7CD1-40A1-A72B-8B8FAC227D51": {
        "Make": "NIKON CORPORATION",
        "Model": "NIKON D810",
        "DateCreated": "2019:04:15",
    },
}
EXIF_UUID_NONE = ["A1DD1F98-2ECD-431F-9AC9-5AFEFE2D3A5C"]

try:
    exiftool = get_exiftool_path()
except:
    exiftool = None

if exiftool is None:
    pytest.skip("could not find exiftool in path", allow_module_level=True)


def test_get_exiftool_path():

    exiftool = dozo.exiftool.get_exiftool_path()
    assert exiftool is not None


def test_version():
    exif = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    assert exif.version is not None
    assert isinstance(exif.version, str)


def test_read():
    exif = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    assert exif.data["File:MIMEType"] == "image/jpeg"
    assert exif.data["EXIF:ISO"] == 160
    assert exif.data["IPTC:Keywords"] == "wedding"


def test_singleton():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    exif2 = dozo.exiftool.ExifTool(TEST_FILE_MULTI_KEYWORD)

    assert exif1._process.pid == exif2._process.pid


def test_pid():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    assert exif1.pid == exif1._process.pid


def test_exiftoolproc_process():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    assert exif1._exiftoolproc.process is not None


def test_exiftoolproc_exiftool():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    assert exif1._exiftoolproc.exiftool == dozo.exiftool.get_exiftool_path()


def test_as_dict():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    exifdata = exif1.asdict()
    assert exifdata["XMP:TagsList"] == "wedding"


def test_as_dict_normalized():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    exifdata = exif1.asdict(normalized=True)
    assert exifdata["xmp:tagslist"] == "wedding"
    assert "XMP:TagsList" not in exifdata


def test_as_dict_no_tag_groups():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    exifdata = exif1.asdict(tag_groups=False)
    assert exifdata["TagsList"] == "wedding"


def test_json():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    exifdata = json.loads(exif1.json())
    assert exifdata[0]["XMP:TagsList"] == "wedding"


def test_str():
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    assert "file: " in str(exif1)
    assert "exiftool: " in str(exif1)


def test_exiftool_terminate():
    """ Test that exiftool process is terminated when exiftool.terminate() is called """
    exif1 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)

    ps = subprocess.run(["ps"], capture_output=True)
    stdout = ps.stdout.decode("utf-8")
    assert "exiftool" in stdout

    dozo.exiftool.terminate_exiftool()

    ps = subprocess.run(["ps"], capture_output=True)
    stdout = ps.stdout.decode("utf-8")
    assert "exiftool" not in stdout

    # verify we can create a new instance after termination
    exif2 = dozo.exiftool.ExifTool(TEST_FILE_ONE_KEYWORD)
    assert exif2.asdict()["IPTC:Keywords"] == "wedding"
