from ordigi.geolocation import GeoLocation
import pytest

class TestGeoLocation:

    def setup_class(cls):
        cls.loc = GeoLocation()

    def test_coordinates_by_name(self):
        coordinates = self.loc.coordinates_by_name('Sunnyvale, CA')
        assert coordinates['latitude'] == 37.3688301
        assert coordinates['longitude'] == -122.036349

    def test_place_name(self):
        place_name = self.loc.place_name(lat=37.368, lon=-122.03)
        assert place_name['city'] == 'Sunnyvale', place_name

        # Invalid lat/lon
        with pytest.warns(UserWarning):
            place_name = self.loc.place_name(lat=999, lon=999)
            assert place_name == {'default': None}, place_name
