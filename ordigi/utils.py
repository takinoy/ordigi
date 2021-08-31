
from math import radians, cos, sqrt

def distance_between_two_points(lat1, lon1, lat2, lon2):
    # As threshold is quite small use simple math
    # From http://stackoverflow.com/questions/15736995/how-can-i-quickly-estimate-the-distance-between-two-latitude-longitude-points  # noqa
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = list(map(
        radians,
        [lat1, lon1, lat2, lon2]
    ))

    r = 6371000  # radius of the earth in m
    x = (lon2 - lon1) * cos(0.5 * (lat2 + lat1))
    y = lat2 - lat1
    return r * sqrt(x * x + y * y)
