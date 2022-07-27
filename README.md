# Ordigi

## Description

This tool aims to make media files organized among giving pattern. It is based on
exif metadata and use Sqlite database.

Goals:

- Organize your existing collection of photos or others media types into a customizable folder structure.
- Record metadata and other file data to an Sqlite database
- Ability to edit metadata

## Install

Ordigi relies on the great [ExifTool library by Phil Harvey](http://www.sno.phy.queensu.ca/~phil/exiftool/). Make sure is installed.

Clone this repository and install ordigi:

```
pip install .
```

## Usage Instructions

### Client interface

You can invoke several commands from the client interface.

Use `ordigi --help` and `ordigi [command] --help` for usage
instructions. For each command there are several options that can be invoked.

#### Import photos to collection

The default behavior is to move files from one or several sources directories
to your destination directory.  However, if you want to copy use `-c` or
`--copy` flag.

```
ordigi import -c /source1 /source2 /collection
```

#### Sort photos into collection

The `sort` command is essentially the same as import but restricted to the files already into the
collection.

```
ordigi sort /subdir1 /subdir2 /collection
```

#### Compare images into collection

Sort file by similarity:

```
ordigi compare /subdir1 /subdir2 /collection
```

Undo sort files:

```
ordigi compare --revert-compare /subdir1 /subdir2 /collection
```

#### Verify collection against bit rot / data rot

```
ordigi check
```

### Edit metadata and Reorganize by changing location and dates (WIP)

```
ordigi edit --location="Las Vegas, NV" 
ordigi edit --time="2015-04-15"
```

### Configuration

#### Config file

The sample configuration file `ordigi.conf` can be copied to `~/.config/ordigi/ordigi.conf` (default location).

Numerous of option like the folder structure, exclusions and other options can
be configured in this file.

#### Folder structure and name

The folder structure and name can be customized via placeholders, a *f-String like* bracket
keywords. Each keyword can be freely combined in any part of the path
pattern.

Default folder structure:
```
dirs_path=<%Y>/<%m-%b>-<city>-<folder>
name=<%Y%m%d-%H%M%S>-<%u<original_name>|%u<basename>>.%l<ext>
```

Example folder structure:
```
├── 2015
│   ├── 06-Jun-California
│   │   ├── 20150629_163414-img_3900.jpg
│   │   └── 20150629_170706-img_3901.jpg
│   └── Paris
│       └── 20150630_024043-img_3903.jpg
├── 2015
│   ├── 07-Jul-Mountain View
│   │   ├── 20150719_171637-img_9426.jpg
│   │   └── 20150724_190633-img_9432.jpg
└── 2015
│   ├── 09-Sep
    │   ├── 20150927_014138-_dsc8705.dng
    │   └── 20150927_014138-_dsc8705.nef
```

The folder structure use standard unix path separator (`/`). Fallback folder part can be optionally specified using a pipe separator and brackets (`<.*|.*>`).

Valid keywords are:

- Date string like *%Y%m%d* pattern For details of the supported formats see [strftime.org](https://strftime.org/).

- Geolocation info from OpenStreetMap: *country, city, location, state*

- Folder structure of source subdirectories like *folder* or *folders[1:]* pattern,
   similar to python list syntax.

- File data : *basename, ext, name, original_name*
- Exif metadata info: *album, camera_make, camera_model, title*.

- custom string using *custom* keyword.

- Special modifiers *%u*/*%l* for upper/lower case respectively.


The default file path structure would look like `2015/07-Jul-Mountain_View/20150712-142231-original_name.jpg`.


## Retrieving data from media

### EXIF and XMP tags

Ordigi use embedded Exif metadata to organize media files and store them in a Sqlite database.

| Data type | Tags | Notes |
|---|---|---|
| Date Original | EXIF:DateTimeOriginal, H264:DateTimeOriginal, EXIF:ModifyDate, file created, file modified |   |
| Date Created | EXIF:CreateDate, QuickTime:CreationDate, QuickTime:CreateDate, QuickTime:CreationDate-und-US, QuickTime:MediaCreateDate |   |
| Date Modified | 'File:FileModifyDate', 'QuickTime:ModifyDate' |   |
| Location | EXIF:GPSLatitude/EXIF:GPSLatitudeRef, EXIF:GPSLongitude/EXIF:GPSLongitudeRef, XMP:GPSLatitude, Composite:GPSLatitude, XMP:GPSLongitude, Composite:GPSLongitude  | Composite tags are read-only |
| Title | XMP:Title, XMP:DisplayName |   |
| Album | XMP-xmpDM:Album, XMP:Album | XMP:Album is user defined in `configs/ExifTool_config` for backwards compatability |
| Camera Make | EXIF:Make, QuickTime:Make, EXIF:Model, QuickTime:Model |   |


For example, the media date can be retrieved, by order of preference, from
*Date Original*, *Date Created*. Optionally *Date Modified* and even filename *date string* can be used, depending of options used (see `ordigi sort --help`).


### Geolocation info

Ordigi use *location* Exif metadata *Nominatim* geocoder to retrive geolocation info from OpenStreetMap

## Credits
The code is based on [Elodie](https://github.com/jmathai/elodie) media organizer and take inspiration from [SortPhotos](https://github.com/andrewning/sortphotos/blob/master/src/sortphotos.py) and [OSXPhotos](https://github.com/RhetTbull/osxphotos) for the Exiftool module.

