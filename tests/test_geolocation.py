from ordigi.utils import distance_between_two_points
from ordigi.geolocation import GeoLocation
import pytest

class TestGeoLocation:

    def setup_class(cls):
        cls.loc = GeoLocation()

    def test_coordinates_by_name(self):
        coordinates = self.loc.coordinates_by_name('Sunnyvale, CA')
        latitude = coordinates['latitude']
        longitude = coordinates['longitude']
        distance = distance_between_two_points(latitude, longitude, 37.3745086, -122.0581602)

        assert distance <= 3000

    def test_place_name(self):
        place_name = self.loc.place_name(lat=37.368, lon=-122.03)
        assert place_name['city'] == 'Sunnyvale', place_name

        # Invalid lat/lon
        with pytest.warns(UserWarning):
            place_name = self.loc.place_name(lat=999, lon=999)
            assert place_name == {'default': None}, place_name
