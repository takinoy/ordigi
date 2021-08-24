
from os import path

import geopy
from geopy.geocoders import Nominatim, options
import logging

from ordigi import config

__KEY__ = None
__DEFAULT_LOCATION__ = 'Unknown Location'


class GeoLocation:
    """Look up geolocation information for media objects."""

    def __init__(self, geocoder='Nominatim', prefer_english_names=False, timeout=options.default_timeout):
        self.geocoder = geocoder
        self.prefer_english_names = prefer_english_names
        self.timeout = timeout

    def coordinates_by_name(self, name, db, timeout=options.default_timeout):
        # Try to get cached location first
        cached_coordinates = db.get_location_coordinates(name)
        if(cached_coordinates is not None):
            return {
                'latitude': cached_coordinates[0],
                'longitude': cached_coordinates[1]
            }

        # If the name is not cached then we go ahead with an API lookup
        geocoder = self.geocoder
        if geocoder == 'Nominatim':
            locator = Nominatim(user_agent='myGeocoder', timeout=timeout)
            geolocation_info = locator.geocode(name)
            if geolocation_info is not None:
                return {
                    'latitude': geolocation_info.latitude,
                    'longitude': geolocation_info.longitude
                }
        else:
            raise NameError(geocoder)

        return None

    def place_name(self, lat, lon, db, cache=True, logger=logging.getLogger(), timeout=options.default_timeout):
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
        geocoder = self.geocoder
        if geocoder == 'Nominatim':
            geolocation_info = self.lookup_osm(lat, lon, logger, timeout)
        else:
            raise NameError(geocoder)

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


    def lookup_osm(self, lat, lon, logger=logging.getLogger(), timeout=options.default_timeout):

        try:
            locator = Nominatim(user_agent='myGeocoder', timeout=timeout)
            coords = (lat, lon)
            if(self.prefer_english_names):
                lang='en'
            else:
                lang='local'
            locator_reverse = locator.reverse(coords, language=lang)
            if locator_reverse is not None:
                return locator_reverse.raw
            else:
                return None
        except geopy.exc.GeocoderUnavailable or geopy.exc.GeocoderServiceError as e:
            logger.error(e)
            return None
        # Fix *** TypeError: `address` must not be None
        except (TypeError, ValueError) as e:
            logger.error(e)
            return None


