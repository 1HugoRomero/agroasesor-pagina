"""Validación de polígonos GeoJSON y cálculo esférico de superficie."""
import math
from decimal import Decimal
from django.core.exceptions import ValidationError

EARTH_RADIUS = 6378137


def polygon_perimeter(coordinates):
    """Return the closed polygon boundary length in metres on the project sphere."""
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValidationError('El perímetro requiere al menos dos vértices.')
    points = []
    for point in coordinates:
        if not isinstance(point, list) or len(point) != 2:
            raise ValidationError('Cada vértice debe contener longitud y latitud.')
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in point):
            raise ValidationError('Las coordenadas deben ser números finitos.')
        longitude, latitude = point
        if not -180 <= longitude <= 180 or not -85 <= latitude <= 85:
            raise ValidationError('Coordenadas fuera del rango admitido.')
        points.append((math.radians(longitude), math.radians(latitude)))

    distance = 0.0
    for index, (longitude, latitude) in enumerate(points):
        next_longitude, next_latitude = points[(index + 1) % len(points)]
        delta_latitude = next_latitude - latitude
        delta_longitude = next_longitude - longitude
        haversine = (
            math.sin(delta_latitude / 2) ** 2
            + math.cos(latitude) * math.cos(next_latitude) * math.sin(delta_longitude / 2) ** 2
        )
        distance += 2 * EARTH_RADIUS * math.atan2(math.sqrt(haversine), math.sqrt(max(0, 1 - haversine)))
    return Decimal(str(distance)).quantize(Decimal('0.01'))


def coordinates_from_geojson(value):
    if isinstance(value, dict) and value.get('type') == 'Feature':
        value = value.get('geometry')
    if not isinstance(value, dict) or value.get('type') != 'Polygon':
        raise ValidationError('La geometría debe ser un polígono GeoJSON.')
    rings = value.get('coordinates')
    if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
        raise ValidationError('Usa un único anillo exterior, sin huecos.')
    ring = rings[0]
    if len(ring) < 4 or ring[0] != ring[-1]:
        raise ValidationError('El anillo GeoJSON debe estar cerrado.')
    ring = ring[:-1]
    return ring


def polygon_geojson(coordinates):
    if not coordinates:
        return None
    ring = [list(point) for point in coordinates]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {
        'type': 'Feature',
        'properties': {},
        'geometry': {'type': 'Polygon', 'coordinates': [ring]},
    }


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        x1, y1 = first
        x2, y2 = second
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside


def polygon_contains(container, subject):
    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_boundary(point, a, b):
        return (
            abs(orientation(a, b, point)) < 1e-14
            and min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
        )

    for point in subject:
        if not point_in_polygon(point, container) and not any(
            on_boundary(point, a, b) for a, b in zip(container, container[1:] + container[:1])
        ):
            return False
    for a, b in zip(subject, subject[1:] + subject[:1]):
        for c, d in zip(container, container[1:] + container[:1]):
            if orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0:
                return False
    return True


def polygons_overlap(first, second):
    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    for a, b in zip(first, first[1:] + first[:1]):
        for c, d in zip(second, second[1:] + second[:1]):
            ab_c, ab_d = orientation(a, b, c), orientation(a, b, d)
            cd_a, cd_b = orientation(c, d, a), orientation(c, d, b)
            if ab_c * ab_d < 0 and cd_a * cd_b < 0:
                return True
    return point_in_polygon(first[0], second) or point_in_polygon(second[0], first)


def polygon_area(coordinates):
    if not isinstance(coordinates, list) or not 3 <= len(coordinates) <= 200:
        raise ValidationError('El perímetro debe tener entre 3 y 200 vértices.')
    points = []
    for point in coordinates:
        if not isinstance(point, list) or len(point) != 2:
            raise ValidationError('Cada vértice debe contener longitud y latitud.')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point):
            raise ValidationError('Las coordenadas deben ser números finitos.')
        lng, lat = point
        if not -180 <= lng <= 180 or not -85 <= lat <= 85:
            raise ValidationError('Coordenadas fuera del rango admitido.')
        points.append((lng, lat))
    if len(set(points)) != len(points):
        raise ValidationError('No repitas vértices; el cierre del perímetro es automático.')
    if max(p[0] for p in points) - min(p[0] for p in points) >= 180:
        raise ValidationError('El perímetro debe ser local y no cruzar el antimeridiano.')

    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])

    def on_segment(a, b, c):
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

    edges = list(zip(points, points[1:] + points[:1]))
    if all(abs(cross(points[0], points[1], p)) < 1e-14 for p in points[2:]):
        raise ValidationError('El perímetro no puede ser una línea.')
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges)-1):
                continue
            c, d = edges[j]
            x, y, z, w = cross(a,b,c), cross(a,b,d), cross(c,d,a), cross(c,d,b)
            if (x*y < 0 and z*w < 0) or any(abs(v) < 1e-14 and on_segment(*segment) for v, segment in [(x,(a,b,c)),(y,(a,b,d)),(z,(c,d,a)),(w,(c,d,b))]):
                raise ValidationError('El perímetro no puede cruzarse ni tocarse a sí mismo.')
    # Área de triángulos esféricos con un vértice común. Misma esfera que computeArea.
    vectors = [(math.cos(math.radians(lat))*math.cos(math.radians(lng)),
                math.cos(math.radians(lat))*math.sin(math.radians(lng)),
                math.sin(math.radians(lat))) for lng, lat in points]
    dot = lambda a,b: sum(x*y for x,y in zip(a,b))
    origin = vectors[0]
    excess = 0
    for i in range(1, len(vectors)-1):
        b, c = vectors[i], vectors[i+1]
        det = origin[0]*(b[1]*c[2]-b[2]*c[1]) + origin[1]*(b[2]*c[0]-b[0]*c[2]) + origin[2]*(b[0]*c[1]-b[1]*c[0])
        excess += 2*math.atan2(det, 1+dot(origin,b)+dot(b,c)+dot(c,origin))
    area = Decimal(str(abs(excess)*EARTH_RADIUS**2)).quantize(Decimal('0.01'))
    if area < Decimal('1'):
        raise ValidationError('El perímetro debe delimitar al menos 1 m².')
    return area
