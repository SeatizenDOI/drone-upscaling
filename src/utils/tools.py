import json
import rasterio
import geopandas as gpd
from pathlib import Path


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