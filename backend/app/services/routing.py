import math
import heapq
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.services.geo import haversine_km, route_intersects_zones, point_in_zone

# Public OSRM demo server — no key required, no registration needed
OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"


def check_osrm_service() -> Dict[str, Any]:
    """Check the live OSRM endpoint and return a user-facing explanation."""
    test_url = f"{OSRM_BASE_URL}/73.8567,18.5204;74.0183,17.6805"
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(test_url, params={"overview": "false"})
        if response.status_code != 200:
            return {
                "available": False,
                "reason": f"OSRM returned HTTP {response.status_code}.",
                "checked_at": checked_at,
            }
        payload = response.json()
        if payload.get("code") != "Ok":
            return {
                "available": False,
                "reason": f"OSRM responded, but reported status '{payload.get('code', 'unknown')}'.",
                "checked_at": checked_at,
            }
        return {
            "available": True,
            "reason": "Live road routing is available.",
            "checked_at": checked_at,
        }
    except httpx.ConnectError:
        return {
            "available": False,
            "reason": "The routing server could not be reached from this computer.",
            "checked_at": checked_at,
        }
    except httpx.TimeoutException:
        return {
            "available": False,
            "reason": "The routing server took too long to respond.",
            "checked_at": checked_at,
        }
    except Exception as exc:
        return {
            "available": False,
            "reason": f"Routing check failed: {type(exc).__name__}.",
            "checked_at": checked_at,
        }

# Coarse local road corridors used only when the live OSRM service is unavailable.
# These follow the main Pune–Satara–Karad–Kolhapur and Pune–Sangli corridors instead
# of drawing an unsafe straight line through the map.
ROAD_NODES = {
    "bhiwandi": (19.2967, 73.0631),
    "pune": (18.5204, 73.8567),
    "satara": (17.6805, 74.0183),
    "karad": (17.2894, 74.1818),
    "kolhapur": (16.7050, 74.2433),
    "sangli": (16.8524, 74.5815),
}

ROAD_EDGES = [
    ("bhiwandi", "pune"),
    ("pune", "satara"),
    ("pune", "sangli"),
    ("satara", "karad"),
    ("karad", "kolhapur"),
    ("karad", "sangli"),
    ("sangli", "kolhapur"),
]


def _safe_road_segment(start: tuple, end: tuple, zones: List) -> bool:
    """Return False when a road segment crosses an active disaster zone."""
    line = [[start[1], start[0]], [end[1], end[0]]]
    return not route_intersects_zones(line, zones)


def find_local_road_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    zones: List,
) -> Optional[Dict[str, Any]]:
    """Find a safe path through the local road corridor graph.

    This is a deterministic offline safety net, not a replacement for OSRM.
    It keeps the demo on recognizable road corridors when external routing is
    unreachable, and removes any corridor segment that crosses a hazard zone.
    """
    points = dict(ROAD_NODES)
    points["origin"] = (origin_lat, origin_lon)
    points["destination"] = (dest_lat, dest_lon)

    blocked_nodes = {
        name for name, point in ROAD_NODES.items()
        if any(point_in_zone(point[0], point[1], zone) for zone in zones)
    }

    graph = {name: [] for name in points}

    def connect(left: str, right: str) -> None:
        if left in blocked_nodes or right in blocked_nodes:
            return
        start, end = points[left], points[right]
        if not _safe_road_segment(start, end, zones):
            return
        weight = haversine_km(start[0], start[1], end[0], end[1])
        graph[left].append((weight, right))
        graph[right].append((weight, left))

    for left, right in ROAD_EDGES:
        connect(left, right)

    # Attach arbitrary warehouse/camp coordinates to their two nearest hubs.
    for endpoint in ("origin", "destination"):
        nearest = sorted(
            (name for name in ROAD_NODES if name not in blocked_nodes),
            key=lambda name: haversine_km(*points[endpoint], *points[name]),
        )[:2]
        for hub in nearest:
            connect(endpoint, hub)

    queue = [(0.0, "origin")]
    distances = {"origin": 0.0}
    previous = {}
    while queue:
        distance, current = heapq.heappop(queue)
        if current == "destination":
            break
        if distance > distances.get(current, float("inf")):
            continue
        for edge_distance, neighbor in graph[current]:
            new_distance = distance + edge_distance
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                previous[neighbor] = current
                heapq.heappush(queue, (new_distance, neighbor))

    if "destination" not in distances:
        return None

    path = []
    current = "destination"
    while current != "origin":
        path.append(current)
        current = previous[current]
    path.append("origin")
    path.reverse()

    coords = []
    for name in path:
        point = [points[name][1], points[name][0]]
        if not coords or point != coords[-1]:
            coords.append(point)
    distance_km = round(distances["destination"] * 1.08, 2)
    duration_min = round((distance_km / 45.0) * 60, 1)
    return {
        "geometry_coords": coords,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "approximate_route": True,
        "road_network_fallback": True,
    }

# Generates a geometric detour route around active hazard zones (used when OSRM is offline or unavailable)
def generate_hazard_detour(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    zones: List
) -> Dict[str, Any]:
    # Check if the straight-line path intersects any active danger zones
    direct_coords = [[origin_lon, origin_lat], [dest_lon, dest_lat]]
    intersecting_zones = [
        z for z in zones
        if getattr(z, "active", True) and route_intersects_zones(direct_coords, [z])
    ]

    coords = [[origin_lon, origin_lat]]

    if intersecting_zones:
        # Pick the largest intersecting zone as the obstacle to route around
        target_zone = max(intersecting_zones, key=lambda z: z.radius_km)
        z_lat, z_lon = target_zone.center_lat, target_zone.center_lon
        buffer_km = target_zone.radius_km + 2.5  # 2.5 km safety buffer outside zone edge

        # Direction vector from origin to destination
        d_lat = dest_lat - origin_lat
        d_lon = dest_lon - origin_lon
        length = math.sqrt(d_lat**2 + d_lon**2) + 1e-9

        # Perpendicular offset vector (rotated 90 degrees)
        perp_lat = -d_lon / length
        perp_lon = d_lat / length

        # 1 degree of latitude ≈ 111.32 km
        lat_step = (buffer_km / 111.32) * perp_lat
        lon_step = (buffer_km / (111.32 * math.cos(math.radians(z_lat)) + 1e-9)) * perp_lon

        # Waypoint pushed perpendicularly away from zone center
        waypoint_lat = z_lat + lat_step
        waypoint_lon = z_lon + lon_step

        # Build smooth 5-point detour polyline: Origin -> Mid1 -> Detour -> Mid2 -> Destination
        mid1 = [origin_lon * 0.5 + waypoint_lon * 0.5, origin_lat * 0.5 + waypoint_lat * 0.5]
        mid2 = [waypoint_lon * 0.5 + dest_lon * 0.5, waypoint_lat * 0.5 + dest_lat * 0.5]
        coords.extend([mid1, [waypoint_lon, waypoint_lat], mid2])

    coords.append([dest_lon, dest_lat])

    # Compute approximate road distance with 1.25x winding factor and ETA at 55 km/h
    total_km = 0.0
    for i in range(len(coords) - 1):
        total_km += haversine_km(coords[i][1], coords[i][0], coords[i+1][1], coords[i+1][0])
    road_km = round(total_km * 1.25, 2)
    eta_mins = round((road_km / 55.0) * 60, 1)

    return {
        "geometry_coords": coords,
        "distance_km": road_km,
        "duration_min": eta_mins,
        "approximate_route": True
    }

# Decodes a polyline encoded string (used by OSRM route geometry)
def decode_polyline(encoded: str, precision: int = 5) -> List[List[float]]:
    coords = []
    index, lat, lng = 0, 0, 0
    factor = 10 ** precision

    while index < len(encoded):
        for is_lat in [True, False]:
            shift, result = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lat:
                lat += delta
            else:
                lng += delta
        # OSRM returns [lat, lng]; convert to GeoJSON [lon, lat]
        coords.append([round(lng / factor, 6), round(lat / factor, 6)])

    return coords

# Fetches a real road route from the public OSRM demo server (no API key required)
def fetch_osrm_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float
) -> Optional[Dict[str, Any]]:
    # OSRM expects coordinates as {lon},{lat};{lon},{lat}
    coords_str = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    url = f"{OSRM_BASE_URL}/{coords_str}"
    params = {
        "overview": "full",        # Return full geometry (not simplified)
        "geometries": "polyline",  # Encoded polyline format
        "steps": "false"
    }

    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    encoded_geom = route["geometry"]
                    coords = decode_polyline(encoded_geom)
                    dist_km = round(route["distance"] / 1000.0, 2)
                    dur_min = round(route["duration"] / 60.0, 1)

                    return {
                        "geometry_coords": coords,
                        "distance_km": dist_km,
                        "duration_min": dur_min,
                        "approximate_route": False
                    }
    except Exception:
        pass

    return None

# Master routing function: uses OSRM for real road geometry, then applies geometric hazard avoidance on top
def calculate_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    zones: Optional[List] = None
) -> Dict[str, Any]:
    active_zones = [z for z in (zones or []) if getattr(z, "active", True)]
    intersecting = [
        z for z in active_zones
        if route_intersects_zones([[origin_lon, origin_lat], [dest_lon, dest_lat]], [z])
    ]

    # --- Case 1: Route is CLEAR — use OSRM for real road geometry ---
    if not intersecting:
        osrm_result = fetch_osrm_route(origin_lat, origin_lon, dest_lat, dest_lon)
        if osrm_result:
            return osrm_result
        # OSRM unreachable — follow the local road corridor graph.
        local_route = find_local_road_route(origin_lat, origin_lon, dest_lat, dest_lon, active_zones)
        if local_route:
            return local_route
        # Last-resort geometry if the local graph is disconnected.
        return generate_hazard_detour(origin_lat, origin_lon, dest_lat, dest_lon, [])

    # --- Case 2: Route is BLOCKED — compute detour waypoint then fetch OSRM leg-by-leg ---
    target_zone = max(intersecting, key=lambda z: z.radius_km)
    z_lat, z_lon = target_zone.center_lat, target_zone.center_lon
    buffer_km = target_zone.radius_km + 2.5

    d_lat = dest_lat - origin_lat
    d_lon = dest_lon - origin_lon
    length = math.sqrt(d_lat**2 + d_lon**2) + 1e-9
    perp_lat = -d_lon / length
    perp_lon = d_lat / length

    lat_step = (buffer_km / 111.32) * perp_lat
    lon_step = (buffer_km / (111.32 * math.cos(math.radians(z_lat)) + 1e-9)) * perp_lon
    waypoint_lat = z_lat + lat_step
    waypoint_lon = z_lon + lon_step

    # Fetch OSRM route in two legs: Origin -> Detour Waypoint -> Destination
    leg1 = fetch_osrm_route(origin_lat, origin_lon, waypoint_lat, waypoint_lon)
    leg2 = fetch_osrm_route(waypoint_lat, waypoint_lon, dest_lat, dest_lon)

    if leg1 and leg2:
        # Stitch both OSRM legs together into a single continuous route
        combined_coords = leg1["geometry_coords"] + leg2["geometry_coords"]
        total_dist = round(leg1["distance_km"] + leg2["distance_km"], 2)
        total_eta = round(leg1["duration_min"] + leg2["duration_min"], 1)

        return {
            "geometry_coords": combined_coords,
            "distance_km": total_dist,
            "duration_min": total_eta,
            "approximate_route": False
        }

    # OSRM offline — use the local road graph before geometric fallback.
    local_route = find_local_road_route(origin_lat, origin_lon, dest_lat, dest_lon, active_zones)
    if local_route:
        return local_route

    # Last-resort geometry if every safe road corridor is blocked.
    return generate_hazard_detour(origin_lat, origin_lon, dest_lat, dest_lon, active_zones)
