import sys
import logging
import subprocess
import tempfile
import datetime
from fractions import Fraction

from . import __version__

logger = logging.getLogger(__name__)


def delta(td):
    return 86400*td.days + td.seconds

def to_rational(float_):
    if abs(int(float_) - float_) < 0.0001:
        return Fraction(int(float_), 1)

    return Fraction(int(round(float_ * 10000)), 10000)


def calculate_position(filename, datetime, gpx, threshold_seconds=120):
    dist_end = delta(datetime - gpx[-1].time)
    if dist_end > threshold_seconds:
        logger.warning('Timestamp of file %s is more than %d seconds (%ds) after the last known GPS position. Skipping.',
                filename, threshold_seconds, dist_end)
        return None

    dist_start = delta(gpx[0].time - datetime)
    if dist_start > threshold_seconds:
        logger.warning('Timestamp of file %s is more than %d seconds (%ds) before the first known GPS position. Skipping.',
                filename, threshold_seconds, dist_start)
        return None

    candidates = []
    for p in gpx:
        dist = delta(p.time - datetime)
        candidates.append((dist, p))

    right_idx = None
    for i, (dist, _) in enumerate(candidates):
        if dist > 0:
            right_idx = i
            break

    if right_idx is None:
        logger.warning('Could not find GPX positions after file %s. This should not happen and fail earlier. Skipping.', filename)
        return None

    before_dist, before = candidates[right_idx - 1]
    after_dist, after = candidates[right_idx]

    if abs(before_dist) > threshold_seconds:
        logger.warning('Previous GPX timestamp is more than %ds (%ds) before time of file %s. Skipping.',
                threshold_seconds, abs(before_dist), filename)
        return None

    if abs(after_dist) > threshold_seconds:
        logger.warning('Next GPX timestamp is more than %ds (%ds) after time of file %s. Skipping.',
                threshold_seconds, abs(after_dist), filename)
        return None

    # linear interpolation
    dist = abs(before_dist) + abs(after_dist)
    a = abs(after_dist) / dist
    b = 1 - a

    lat = a * before.latitude + b * after.latitude
    lng = a * before.longitude + b * after.longitude
    alt = a * before.elevation + b * after.elevation

    # to DMS
    ns_hemisphere = 'N' if lat >= 0 else 'S'
    ew_hemisphere = 'E' if lng >= 0 else 'W'

    lat_abs = abs(lat)
    ns_deg = int(lat_abs)
    tmp = (lat_abs - ns_deg) * 60
    ns_min = int(tmp)
    ns_sec = round((tmp - ns_min) * 60, 2)

    lng_abs = abs(lng)
    ew_deg = int(lng_abs)
    tmp = (lng_abs - ew_deg) * 60
    ew_min = int(tmp)
    ew_sec = round((tmp - ew_min) * 60, 2)

    logger.info('Determined position %s %d° %d\' %.5f", %s %d° %d\' %.5f" for file %s (prev %ds, next %ds).',
            ns_hemisphere, ns_deg, ns_min, ns_sec,
            ew_hemisphere, ew_deg, ew_min, ew_sec,
            filename, before_dist, after_dist)

    return {
            'Exif.Image.GPSTag': 1,
            'Exif.GPSInfo.GPSProcessingMethod': F'geopinner/{__version__}: https://github.com/mfranke93/geopinner',
            'Exif.GPSInfo.GPSVersionID': bytes((2, 0, 0, 0)),
            'Exif.GPSInfo.GPSAltitudeRef': 0,  # above sea level
            'Exif.GPSInfo.GPSAltitude': to_rational(round(alt)),
            'Exif.GPSInfo.GPSLatitudeRef': ns_hemisphere,
            'Exif.GPSInfo.GPSLatitude': (
               to_rational(ns_deg),
               to_rational(ns_min),
               to_rational(ns_sec),
               ),
            'Exif.GPSInfo.GPSLongitudeRef': ew_hemisphere,
            'Exif.GPSInfo.GPSLongitude': (
                to_rational(ew_deg),
                to_rational(ew_min),
                to_rational(ew_sec),
                ),
            }


def to_string(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, bytes):
        return ' '.join(map(str, value))
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, Fraction):
        return F'{value.numerator}/{value.denominator}'
    elif isinstance(value, (list, tuple)):
        return ' '.join(map(to_string, value))
    else:
        raise ValueError(F'Unprocessable entity of type {type(value)}: {value}')



def geolocate_image(img, gpx, dry_run=False, tzinfo=None, threshold_seconds=120):
    dt_raw = subprocess.check_output(['exiv2', '-K', 'Exif.Image.DateTime', '-Pt', img.name],
            encoding='utf-8')
    dt = datetime.datetime.strptime(dt_raw.strip(), '%Y:%m:%d %H:%M:%S').replace(tzinfo=tzinfo)

    exifdata = calculate_position(img.name, dt, gpx, threshold_seconds=threshold_seconds)
    if exifdata is None:
        return False

    if dry_run:
        logger.debug('Will not update metadata of file %s.', img.name)

    else:
        with tempfile.NamedTemporaryFile(mode='w') as tmp:
            for k, v in exifdata.items():
                tmp.write(F'set {k} {to_string(v)}\n')

            tmp.flush()

            subprocess.run(['exiv2', '-m', tmp.name, img.name], check=True)
            logger.debug('Updated metadata of file %s.', img.name)

    return True
