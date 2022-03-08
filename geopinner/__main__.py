#!/usr/bin/env python3

import sys
import argparse
import logging
from zoneinfo import ZoneInfo, available_timezones
import subprocess

from .gpx import load_gpx
from .image import geolocate_image

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')
    logger = logging.getLogger(vars(sys.modules[__name__])['__package__'])
    logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--dry-run', action='store_const', const=True, default=False, help='do not write anything')
    parser.add_argument('--tz', '--time-zone', dest='time_zone', metavar='<IANA TZ name>', type=str, action='store', default='Europe/Berlin', choices=available_timezones(), help='time zone the images\' EXIF timestamps are in')
    parser.add_argument('-t', '--threshold', metavar='<seconds>', type=int, action='store', default=120, help='maximum time difference to GPX points allowed')
    parser.add_argument('--gpx', metavar='<GPX file>', type=argparse.FileType('r'), nargs='+', default=[], help='GPX files to use for pinning')
    parser.add_argument('--images', metavar='<image file>', type=argparse.FileType('rb'), nargs='+', default=[], help='image files to process')
    parsed = parser.parse_args()

    # check that exiv2 is installed
    try:
        subprocess.run(['which', 'exiv2'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        logger.error('exiv2 is not installed on the system, but is required to run geopinner.')
        sys.exit(1)

    tzinfo = ZoneInfo(parsed.time_zone)

    if parsed.dry_run:
        logger.info('Dry run. Will not write changes to image files.')

    gpx = load_gpx(parsed.gpx)

    skipped_images = []
    for img in parsed.images:
        rv = geolocate_image(img, gpx, dry_run=parsed.dry_run, tzinfo=tzinfo, threshold_seconds=parsed.threshold)
        if not rv:
            skipped_images.append(img.name)

    if len(skipped_images) > 0:
        imgnames = '\n'.join(map(lambda s: F'\t{s}', skipped_images))
        logger.warning('The following images were skipped because no GPX data for that time was available:\n\n%s\n', imgnames)

