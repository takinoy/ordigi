"""Look up geolocation information for media objects."""
from past.utils import old_div


from os import path

import geopy
from geopy.geocoders import Nominatim
import logging

from dozo import constants
from dozo.config import load_config, get_geocoder

__KEY__ = None
__DEFAULT_LOCATION__ = 'Unknown Location'
__PREFER_ENGLISH_NAMES__ = None


def coordinates_by_name(name, db):
    # Try to get cached location first
    cached_coordinates = db.get_location_coordinates(name)
    if(cached_coordinates is not None):
        return {
            'latitude': cached_coordinates[0],
            'longitude': cached_coordinates[1]
        }

    # If the name is not cached then we go ahead with an API lookup
    geocoder = get_geocoder()
    if geocoder == 'Nominatim':
        locator = Nominatim(user_agent='myGeocoder')
        geolocation_info = locator.geocode(name)
        if geolocation_info is not None:
            return {
                'latitude': geolocation_info.latitude,
                'longitude': geolocation_info.longitude
            }

    return None


def decimal_to_dms(decimal):
    decimal = float(decimal)
    decimal_abs = abs(decimal)
    minutes, seconds = divmod(decimal_abs*3600, 60)
    degrees, minutes = divmod(minutes, 60)
    degrees = degrees
    sign = 1 if decimal >= 0 else -1
    return (degrees, minutes, seconds, sign)


def dms_to_decimal(degrees, minutes, seconds, direction=' '):
    sign = 1
    if(direction[0] in 'WSws'):
        sign = -1
    return (
        float(degrees) + old_div(float(minutes), 60) +
        old_div(float(seconds), 3600)
    ) * sign


def dms_string(decimal, type='latitude'):
    # Example string -> 38 deg 14' 27.82" S
    dms = decimal_to_dms(decimal)
    if type == 'latitude':
        direction = 'N' if decimal >= 0 else 'S'
    elif type == 'longitude':
        direction = 'E' if decimal >= 0 else 'W'
    return '{} deg {}\' {}" {}'.format(dms[0], dms[1], dms[2], direction)


def get_prefer_english_names():
    global __PREFER_ENGLISH_NAMES__
    if __PREFER_ENGLISH_NAMES__ is not None:
        return __PREFER_ENGLISH_NAMES__

    config = load_config(constants.CONFIG_FILE)
    if('prefer_english_names' not in config['Geolocation']):
        return False

    __PREFER_ENGLISH_NAMES__ = bool(config['Geolocation']['prefer_english_names'])
    return __PREFER_ENGLISH_NAMES__

def place_name(lat, lon, db, cache=True, logger=logging.getLogger()):
    lookup_place_name_default = {'default': __DEFAULT_LOCATION__}
    if(lat is None or lon is None):
        return lookup_place_name_default

    # Convert lat/lon to floats
    if(not isinstance(lat, float)):
        lat = float(lat)
    if(not isinstance(lon, float)):
        lon = float(lon)

    # Try to get cached location first
    # 3km distace radious for a match
    cached_place_name = None
    if cache:
        cached_place_name = db.get_location_name(lat, lon, 3000)
    # We check that it's a dict to coerce an upgrade of the location
    #  db from a string location to a dictionary. See gh-160.
    if(isinstance(cached_place_name, dict)):
        return cached_place_name

    lookup_place_name = {}
    geocoder = get_geocoder()
    if geocoder == 'Nominatim':
        geolocation_info = lookup_osm(lat, lon, logger)
    else:
        return None

    if(geolocation_info is not None and 'address' in geolocation_info):
        address = geolocation_info['address']
        # gh-386 adds support for town
        # taking precedence after city for backwards compatability
        for loc in ['city', 'town', 'village', 'state', 'country']:
            if(loc in address):
                lookup_place_name[loc] = address[loc]
                # In many cases the desired key is not available so we
                #  set the most specific as the default.
                if('default' not in lookup_place_name):
                    lookup_place_name['default'] = address[loc]

    if(lookup_place_name):
        db.add_location(lat, lon, lookup_place_name)
        # TODO: Maybe this should only be done on exit and not for every write.
        db.update_location_db()

    if('default' not in lookup_place_name):
        lookup_place_name = lookup_place_name_default

    return lookup_place_name

def lookup_osm(lat, lon, logger=logging.getLogger()):

    prefer_english_names = get_prefer_english_names()
    from geopy.geocoders import Nominatim
    try:
        locator = Nominatim(user_agent='myGeocoder')
        coords = (lat, lon)
        if(prefer_english_names):
            lang='en'
        else:
            lang='local'
        return locator.reverse(coords, language=lang).raw
    except geopy.exc.GeocoderUnavailable as e:
        logger.error(e)
        return None
    except ValueError as e:
        logger.error(e)
        return None


