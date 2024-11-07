import json
import numpy as np
import pandas as pd
from tqdm import tqdm
from osgeo import gdal
import geopandas as gpd
from pathlib import Path
from argparse import Namespace
from shapely.geometry import box

import rasterio
from rasterio.windows import Window



from ..utils.tools import get_config_env, check_crs

class Orthophoto:

    def __init__(self, args: Namespace) -> None:

        self.args = args
        self.config_env = get_config_env(self.args.config_path)
        
        # All path variable not defined in constructor are defined in setup and nowhere else.
        self.setup()


    def setup(self) -> None:
        """ Setup all path and check if file exist. """
        self.folder_path = Path(self.config_env["DRONE_PATH"])

        # Orthophoto path.
        self.orthophoto_filepath = Path(self.folder_path, "odm_orthophoto", "odm_orthophoto.tif")
        if not self.orthophoto_filepath.exists() or not self.orthophoto_filepath.is_file():
            raise NameError(f"Orthophoto not found at path: {self.orthophoto_filepath}")
        
        # Stats path.
        self.stats_filepath = Path(self.folder_path, "odm_report", "stats.json")
        if not self.stats_filepath.exists() or not self.stats_filepath.is_file():
            raise NameError(f"Stats not found at path: {self.stats_filepath}")
        
        # Get GSD mean.
        with open(self.stats_filepath, "r") as stat_file:
            stats = json.load(stat_file)
            try:
                self.GSD_mean = round(stats["odm_processing_statistics"]["average_gsd"], 2)
            except:
                raise NameError("Cannot get GSD value")
        
        # Check if orthophoto is in the correct crs.
        with rasterio.open(self.orthophoto_filepath) as ortho:
            if not check_crs(ortho, self.args.matching_crs):
                raise NameError(f"Orthophoto crs doesn't match with desired args {self.args.matching_crs}")
    
    
    def setup_ortho_tiles(self, drone_preprocess_tif_folder: Path, drone_filtred_png_folder: Path):

        bounds = self.split_tif_into_tiles(drone_preprocess_tif_folder)
        filtered_bounds_on_manual_boundary_df = self.filter_tiles_based_on_manual_boundary(bounds)
        self.convert_tif_to_png(drone_filtred_png_folder, filtered_bounds_on_manual_boundary_df)

    
    def convert_tif_to_png(self, drone_filtred_png_folder: Path, filtered_bounds_on_manual_boundary_df: pd.DataFrame) -> None:
        print("\n\n-- func: Convert TIF Files to png files.")
        
        # Mandatory by gdal warning.
        gdal.DontUseExceptions()

        # Convert each tif image in the input directory to png format.
        for i, row in filtered_bounds_on_manual_boundary_df.iterrows():
            input_path = Path(row["tile_filename"])
            output_path = Path(drone_filtred_png_folder, row["tile_png"])

            with gdal.Open(input_path) as src_ds:
                gdal.Translate(output_path, src_ds, format='PNG')
        
        print("\n-- func: Conversion to PNG completed.")

        # After all the conversions are done, remove the .aux.xml files.
        for aux_file in drone_filtred_png_folder.iterdir():
            if ".aux.xml" in aux_file.name.lower():
                aux_file.unlink()
        
        print("\n-- func: All auxiliary .aux.xml files have been removed.")


    def filter_tiles_based_on_manual_boundary(self, bounds_df: pd.DataFrame) -> pd.DataFrame:
        print("\n\n-- func: Filter tiles based on manual boundary.")
        
        manual_boundary_path = Path(self.config_env["MANUEL_BOUNDARY_PATH"])
        if not manual_boundary_path.exists():
            raise NameError(f"Manual boundary file not found at path {manual_boundary_path}")

        polygon_df = gpd.read_file(manual_boundary_path)

        # Assuming there's only one polygon in the GeoJSON
        polygon = polygon_df.geometry.iloc[0]

        # Assuming tile_bounds is a list of tuples/lists in the format [(minx, miny, maxx, maxy), ...]
        def is_bounds_in_polygon(row):
            """ If bounds in polygon, convert tif name to png name else return '' """

            minx, miny, maxx, maxy = row["bounds"]
            if polygon.contains(box(minx, miny, maxx, maxy).centroid):
                return f"odm_orthophoto_{int(minx)}_{int(maxy)}.png"
            return ""

        bounds_df["tile_png"] = bounds_df.apply(is_bounds_in_polygon, axis=1)

        return bounds_df[bounds_df["tile_png"] != ""].reset_index()


    def split_tif_into_tiles(self, output_dir: Path) -> pd.DataFrame:
        print("\n\n-- func: Split tif into tiles.")
        
        tile_size = int(self.args.tiles_size_meters // (self.GSD_mean / 100))
        size_inline_tile = tile_size**2
        x_overlap = int(tile_size * self.args.h_shift)
        y_overlap = int(tile_size * self.args.v_shift)
 
        bounds_list = []
        with rasterio.open(self.orthophoto_filepath) as src:

            for i in tqdm(range(0, src.height, tile_size - y_overlap)):
                for j in range(0, src.width, tile_size - x_overlap):
                    window = Window(j, i, tile_size, tile_size)

                    transform_window = src.window_transform(window)
                    
                    tile = src.read(window=window, indexes=[1, 2, 3])

                    # Apply threshold to avoid keep useless image.                    
                    greyscale_tile = np.sum(tile, axis=0) / 3
                    
                    # Black threshold.
                    percentage_black_pixel = np.sum(greyscale_tile == 0) * 100 / size_inline_tile
                    if percentage_black_pixel > self.args.black_pixels_threshold_percentage:
                        continue

                    # White threshold.
                    percentage_white_pixel = np.sum(greyscale_tile == 255) * 100 / size_inline_tile
                    if percentage_white_pixel > self.args.white_pixels_threshold_percentage:
                        continue

                    tile_filename = Path(output_dir / f"tile_{i}_{j}.tif")
                    
                    with rasterio.open(
                        tile_filename, "w",
                        driver="GTiff",
                        height=tile.shape[1],
                        width=tile.shape[2],
                        count=3,
                        dtype=tile.dtype,
                        crs=src.crs,
                        transform=transform_window
                    ) as dst:
                        dst.write(tile)
                        bounds_list.append((tile_filename, dst.bounds))
                
                if (i / (tile_size - y_overlap)  >= 1): break

        bounds_df = pd.DataFrame(bounds_list, columns=["tile_filename", "bounds"])
        print(f"Tiles generated: {len(bounds_df)}")
        
        return bounds_df
