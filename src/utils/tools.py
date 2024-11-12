import json
import rasterio
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from functools import partial
from pyproj import Transformer
from shapely.ops import transform
from shapely.geometry import Point, Polygon
from math import radians, atan2, pi, asin, sin, cos, degrees

from ..lib.CameraCalculator import CameraCalculator


def get_config_env(config_path: str) -> dict[str, str]:
    """ Load config env """
    config_path = Path(config_path)
    if not config_path.exists() or not config_path.is_file():
        raise NameError(f"Config file not found for path {config_path}")

    with open(config_path, 'r') as file:
        config_env: dict[str, str] = json.load(file)
    
    return config_env


def check_crs(obj: gpd.GeoDataFrame | rasterio.io.DatasetReader, crs_code: str):
    """ Check if the layers provided are set to the correct CRS.

    Args:
        obj : a raster or vector layer read with rasterio or geopandas
        crs_code (str) : the CRS number to check

    Returns: 
        True or False. True means that CRS of the layer is the one expected.
    """
    return obj.crs == rasterio.crs.CRS.from_epsg(crs_code)


def dest_from_start(lat1, lon1, d, bearing) :
    # Inputs :
    # 1.lat1 = latitude of the starting point in degrees
    # 2.lon1 = longitude of the starting point in degrees
    # 3.d = distance from the starting point in m
    # 4.bearing = direction from one place to another in degrees
    
    # Outputs :
    # 1.lat2 = latitude of the destination point in degrees
    # 2.lon2 = longitude of the destination point in degrees
    
    # we'll do all the computations in KM for a sake of simplicity
    d = d * 1e-3
    R = 6378.137 # Radius of earth in KM
    ang_dist = d/R
    # CAVEAT : we'll do all the computations in radians for a sake of simplicity
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    bearing = radians(bearing)
    
    lat2 = asin( sin(lat1) * cos(ang_dist) + cos(lat1) * sin(ang_dist) * cos(bearing) )
    # Python reverses the arguments of ATAN2 wrt the function "Destination point given distance 
    # and bearing from start point" in :
    # https://www.movable-type.co.uk/scripts/latlong.html
    lon2 = lon1 + atan2(  sin(bearing) * sin(ang_dist) * cos(lat1) , cos(ang_dist) - sin(lat1) * sin(lat2))
    #
    lat2 = degrees(lat2)
    lon2 = degrees(lon2)
    return lat2, lon2
    

def get_dist_and_angle(p, q):
    # Check if either point is empty
    if p.is_empty or q.is_empty:
        return None, None

    try:
        angle = atan2(q.y - p.y, q.x - p.x) * 180 / pi
        d = ((((q.x - p.x)**2) + ((q.y - p.y)**2) )**0.5)
        return d, angle
    except Exception as e:
        print(f"Error processing points {p} and {q}: {e}")
        return None, None


# Example usage of the calculate_footprint function
def calculate_footprint(row, fov_x, fov_y, target_crs):
    c = CameraCalculator()
    lat1 = row['GPSLatitude']
    lon1 = row['GPSLongitude']
    bbox = c.getBoundingPolygon(radians(fov_x), radians(fov_y),
                                row['GPSAltitude'], radians(row['GPSRoll']),
                                radians(row['GPSPitch']), radians(row['GPSTrack']))

    lat_vec = []
    lon_vec = []
    p1 = Point(0, 0)

    for i, p in enumerate(bbox):
        if p.x is None or p.y is None:
            continue  # Skip invalid points
        p2 = Point(p.x, p.y)
        if p2.is_empty:
            continue  # Skip empty points

        d, angle = get_dist_and_angle(p1, p2)
        if d is None or angle is None:
            continue  # Skip if unable to calculate distance or angle

        lat2, lon2 = dest_from_start(lat1, lon1, d, angle)
        lat_vec.append(lat2)
        lon_vec.append(lon2)

    footprint_geo = Polygon(zip(lon_vec, lat_vec))
    transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    footprint_projected = transform(partial(transformer.transform), footprint_geo)

    return footprint_projected

# Function to calculate the probability for a single class
def calculate_probability_from_binary_fine_scale(df, class_name):
    # Filter rows where the class is True
    df_class = df[df[class_name]]
    if df_class.empty:
        return 0.0
    
    # Calculate the product term for the given class
    product_term = np.prod([
        (row['UnderwaterImageArea'] - row['IntersectionArea']) / row['UnderwaterImageArea']
        for _, row in df_class.iterrows()
        if not pd.isna(row['UnderwaterImageArea']) and not pd.isna(row['IntersectionArea'])
    ])
    
    # Calculate the final probability
    P_presence = 1 - product_term
    return P_presence

def calculate_probability_from_probs_fine_scale(df, class_name):
    # Calculate the product term for the given class, incorporating probabilities
    product_term = np.prod([
        1 - (row[class_name] * row['IntersectionArea'] / row['UnderwaterImageArea'])
        for _, row in df.iterrows()
        if not pd.isna(row['UnderwaterImageArea']) and not pd.isna(row['IntersectionArea']) and not pd.isna(row[class_name])
    ])
    
    # Calculate the final probability
    P_presence = 1 - product_term
    return P_presence