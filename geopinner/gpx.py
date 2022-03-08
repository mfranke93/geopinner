import gpxpy
import logging

def load_gpx(files):
    points = []

    for file in files:
        gpx = gpxpy.parse(file)
        for track in gpx.tracks:
            for segment in track.segments:
                points += segment.points

    points.sort(key=lambda p:p.time)

    logging.getLogger(__name__).info('Loaded %d GPX points from %d files.', len(points), len(files))
    return points
