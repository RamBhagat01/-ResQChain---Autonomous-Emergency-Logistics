import math
from typing import List, Tuple
from shapely.geometry import Point, Polygon, LineString

# Calculate great-circle distance in kilometers between two GPS points using Haversine formula
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Convert a center coordinate and radius into a Shapely polygon in [lon, lat] order
def circle_to_polygon(lat: float, lon: float, radius_km: float, n_points: int = 32) -> Polygon:
    coords = []
    # 1 degree of latitude is approx 111.32 km
    lat_deg_per_km = 1.0 / 111.32
    # 1 degree of longitude depends on latitude
    lon_deg_per_km = 1.0 / (111.32 * math.cos(math.radians(lat)) + 1e-9)

    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        dx = radius_km * math.cos(angle)
        dy = radius_km * math.sin(angle)
        pt_lat = lat + dy * lat_deg_per_km
        pt_lon = lon + dx * lon_deg_per_km
        coords.append((pt_lon, pt_lat))  # GeoJSON standard: [lon, lat]
    coords.append(coords[0])  # Close the polygon ring
    return Polygon(coords)

# Check if a single point (lat, lon) falls inside a danger zone
def point_in_zone(lat: float, lon: float, zone) -> bool:
    dist = haversine_km(lat, lon, zone.center_lat, zone.center_lon)
    return dist <= zone.radius_km

# Check if a route's coordinate line intersects any active danger zones
def route_intersects_zones(route_coords: List[List[float]], zones: List) -> bool:
    if not route_coords or len(route_coords) < 2:
        return False

    # Route coords are assumed to be [lon, lat] pairs (GeoJSON standard)
    route_line = LineString([(pt[0], pt[1]) for pt in route_coords])

    for zone in zones:
        if not getattr(zone, "active", True):
            continue
        poly = circle_to_polygon(zone.center_lat, zone.center_lon, zone.radius_km)
        if route_line.intersects(poly):
            return True
    return False
