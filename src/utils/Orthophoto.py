import json
import shutil
import numpy as np
import pandas as pd
from tqdm import tqdm
from osgeo import gdal
import geopandas as gpd
from pathlib import Path
from argparse import Namespace
from pyproj import Transformer
from shapely.geometry import box

import rasterio
from rasterio.windows import Window

from .tools import check_crs
from .BaseManager import BaseManager

class Orthophoto(BaseManager):

    def __init__(self, args: Namespace) -> None:
        BaseManager.__init__(self, args)
        
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
    
    
    def setup_ortho_tiles(self) -> pd.DataFrame:
        csv_path = Path(self.output_folder, 'filtered_bounds_on_manual_boundary_df.csv')
        bounds = self.split_tif_into_tiles()
        filtered_bounds_on_manual_boundary_df = self.filter_tiles_based_on_manual_boundary(bounds)
        self.convert_tif_to_png(filtered_bounds_on_manual_boundary_df)
        filtered_bounds_on_manual_boundary_df.to_csv(csv_path, index=False)
        return filtered_bounds_on_manual_boundary_df
    

    def convert_tif_to_png(self, filtered_bounds_on_manual_boundary_df: pd.DataFrame) -> None:
        print("\n\n-- func: Convert TIF Files to png files.")
        
        # Mandatory by gdal warning.
        gdal.DontUseExceptions()

        # Convert each tif image in the input directory to png format.
        for i, row in tqdm(filtered_bounds_on_manual_boundary_df.iterrows(), total=len(filtered_bounds_on_manual_boundary_df)):
            # Rename tif file to match png filename
            input_path = Path(row["tile_filename"].parent, f'{row["tile_png"]}.tif')
            output_path = Path(self.tiles_png_folder, f'{row["tile_png"]}.png')

            shutil.move(row["tile_filename"], input_path)

            with gdal.Open(str(input_path)) as src_ds:
                gdal.Translate(output_path, src_ds, format='PNG')
        
        print("-- func: Conversion to PNG completed.")

        # After all the conversions are done, remove the .aux.xml files.
        for aux_file in self.tiles_png_folder.iterdir():
            if ".aux.xml" in aux_file.name.lower():
                aux_file.unlink()
        
        print("-- func: All auxiliary .aux.xml files have been removed.")


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
            
            if polygon.contains(row["bounds_polygon"].centroid):
                return f"odm_orthophoto_{int(row["bounds_polygon"].centroid.x)}_{int(row["bounds_polygon"].centroid.y)}"
            return ""

        bounds_df["tile_png"] = bounds_df.apply(is_bounds_in_polygon, axis=1)
        
        return bounds_df[bounds_df["tile_png"] != ""].reset_index()


    def split_tif_into_tiles(self) -> pd.DataFrame:
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

                    tile_filename = Path(self.tiles_folder / f"tile_{i}_{j}.tif")
                    
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
                        bounds_list.append((tile_filename, box(*dst.bounds)))

        bounds_df = pd.DataFrame(bounds_list, columns=["tile_filename", "bounds_polygon"])
        print(f"Tiles generated: {len(bounds_df)}")
        
        if len(bounds_df) == 0: 
            raise NameError("Not enough tiles to continue")

        return bounds_df

    def create_unlabeled_csv(self, unlabeled_folder: Path, tiles_bound_df: pd.DataFrame):
        print("\n\n-- func: Create unlabeled CSV.")
        transformer = Transformer.from_crs("epsg:32740", "epsg:4326", always_xy=True)  # Adjust the EPSG codes as needed

        # Prepare CSV for GPS information
        csv_path = Path(self.output_folder, 'unlabeled_images_geolocations.csv')
        geolocations = []  # List to hold the geolocation data

        tiles_bound_df.set_index("tile_png", inplace=True)

        # Convert TIFF to PNG and extract GPS information
        for filename in tqdm(unlabeled_folder.iterdir()):
            if filename.suffix.lower() != ".png": continue

            file_tif = Path(tiles_bound_df.loc[filename.stem]["tile_filename"].parent, f'{filename.stem}.tif')
            # Open the input file and retrieve geotransform data
            with gdal.Open(file_tif) as src_ds:
                gt = src_ds.GetGeoTransform()
                width = src_ds.RasterXSize
                height = src_ds.RasterYSize

                # Calculate the coordinates of the image centroid
                centroid_x = gt[0] + (width * gt[1] / 2) + (height * gt[2] / 2)
                centroid_y = gt[3] + (width * gt[4] / 2) + (height * gt[5] / 2)

                # Convert from projected coordinates (UTM) to geographic coordinates (lat, lon)
                lon, lat = transformer.transform(centroid_x, centroid_y)

                # Append the data to the list
                geolocations.append({
                    'FileName': filename.name,
                    'GPSLatitude': lat,
                    'GPSLongitude': lon
                })

        # Save geolocation data to CSV
        df_geo = pd.DataFrame(geolocations)
        df_geo.to_csv(csv_path, index=False)

        print("-- func: Geolocation extraction completed. Data saved to:", csv_path)
