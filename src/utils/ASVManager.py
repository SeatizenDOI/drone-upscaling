import pandas as pd
from tqdm import tqdm
import geopandas as gpd
from pathlib import Path
from argparse import Namespace
from shapely.ops import unary_union

from .tools import calculate_footprint
from .BaseManager import BaseManager

class ASVManager(BaseManager):

    def __init__(self, args: Namespace) -> None:
        BaseManager.__init__(self, args)
        
        self.annotations_plancha_filtered = gpd.GeoDataFrame()

    def compute_annotations(self, save_folder: Path, tiles_bounds: pd.DataFrame) -> gpd.GeoDataFrame:
        self.filter_annotation_asv(save_folder)
        annotations_tiles = self.match_asv_annotations_with_tiles(save_folder, tiles_bounds)
        annotation_tiles_gdf = self.compute_footprint(annotations_tiles)

        annotation_tiles_gdf_filtered = self.filter_tiles_enough_underwater_coverage(annotation_tiles_gdf)

        return annotation_tiles_gdf_filtered

    def filter_tiles_enough_underwater_coverage(self, annotation_tiles_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        print("\n\n-- func: Filter tiles with enough underwater coverage.")
        
        merged_footprints = annotation_tiles_gdf.groupby('FileName')['UnderwaterImageFootprint'].apply(unary_union).reset_index()
        merged_footprints_gdf = gpd.GeoDataFrame(merged_footprints, geometry='UnderwaterImageFootprint')
        merged_footprints_gdf.set_geometry('UnderwaterImageFootprint', inplace=True)
        annotation_tiles_gdf.set_geometry('tile_bounds', inplace=True)
        # Join the original gdf with the merged_footprints_gdf on FileName to get tile_bounds
        merged_data = annotation_tiles_gdf.drop('UnderwaterImageFootprint', axis=1).merge(merged_footprints_gdf, on='FileName').copy()
        # Calculate the intersection with the tile_bounds for each row
        # Calculate the intersection
        merged_data['Intersection'] = merged_data.apply(
            lambda row: row['tile_bounds'].intersection(row['UnderwaterImageFootprint']), axis=1
        )
        # Calculate the area of the intersection polygon
        # Note: This assumes that the geometries are in a CRS that uses meters for distance measurements.
        # If they are in a geographic CRS (lat/lon), you will need to project them to a suitable projected CRS before calculating the area.
        merged_data['IntersectionArea'] = merged_data['Intersection'].apply(lambda x: x.area)
        merged_data['TileArea'] = merged_data['tile_bounds'].apply(lambda x: x.area)
        tiles_above_threshold = merged_data[merged_data['IntersectionArea']/merged_data['TileArea'] >= self.args.footprint_threshold]
        tiles_above_threshold = tiles_above_threshold.set_geometry('tile_bounds')
        # filter annotation_tiles_gdf on the basis of images that are in tiles_above_threshold
        annotation_tiles_gdf_filtered = annotation_tiles_gdf[annotation_tiles_gdf['FileName'].isin(tiles_above_threshold['FileName'])].copy()
        # Calculate the intersection with the tile_bounds for each row
        annotation_tiles_gdf_filtered['Intersection'] = annotation_tiles_gdf_filtered.apply(
            lambda row: row['tile_bounds'].intersection(row['UnderwaterImageFootprint']) if row['tile_bounds'] is not None and row['UnderwaterImageFootprint'] is not None else None, axis=1
        )
        # Calculate the area of the intersection polygon
        # Note: This assumes that the geometries are in a CRS that uses meters for distance measurements.
        # If they are in a geographic CRS (lat/lon), you will need to project them to a suitable projected CRS before calculating the area.
        #annotation_tiles_gdf['IntersectionArea'] = annotation_tiles_gdf['Intersection'].apply(lambda x: x.area if x is not None else None)
        annotation_tiles_gdf_filtered['TileArea'] = annotation_tiles_gdf_filtered['tile_bounds'].apply(lambda x: x.area if x is not None else None)
        annotation_tiles_gdf_filtered['UnderwaterImageArea'] = annotation_tiles_gdf_filtered['UnderwaterImageFootprint'].apply(lambda x: x.area if x is not None else None)
        annotation_tiles_gdf_filtered['IntersectionArea'] = annotation_tiles_gdf_filtered['Intersection'].apply(lambda x: x.area if x is not None else None)
        # set the correct geometry for tiles
        annotation_tiles_gdf_filtered = annotation_tiles_gdf_filtered.set_geometry('tile_bounds')

        return annotation_tiles_gdf_filtered


    def compute_footprint(self, annotation_tiles: pd.DataFrame) -> gpd.GeoDataFrame:
        print("\n\n-- Compute footprint for each ASV frame.")
        if not self.asv_metadata_path.exists() or not self.asv_metadata_path.is_file():
            raise NameError(f"Orthophoto not found at path: {self.asv_metadata_path}")
        
        asv_metadata_df = pd.read_csv(self.asv_metadata_path)
        
        frames_to_compute = list(set(annotation_tiles["PlanchaFileName"].to_list()))

        sub_asv_metadata_df = asv_metadata_df[asv_metadata_df["FileName"].isin(frames_to_compute)]

        sub_asv_metadata_df["footprint"] = sub_asv_metadata_df.apply(lambda row: calculate_footprint(row, self.args.fov_x, self.args.fov_y, self.args.matching_crs), axis=1)

        sub_asv_metadata_gdf = gpd.GeoDataFrame(sub_asv_metadata_df, geometry='footprint').set_index("FileName")

        # Prepare an empty list to hold the footprints
        footprints = [sub_asv_metadata_gdf.loc[row['PlanchaFileName']]['footprint'] if row['PlanchaFileName'] in sub_asv_metadata_gdf.index else None for idx, row in tqdm(annotation_tiles.iterrows(), total=len(annotation_tiles))]

        annotation_tiles_gdf = gpd.GeoDataFrame(annotation_tiles, geometry='geometry', crs=self.args.matching_crs)
        annotation_tiles_gdf['UnderwaterImageFootprint'] = footprints
        
        return annotation_tiles_gdf


    def filter_annotation_asv(self, save_folder: Path) -> None:
        print("\n\n-- func: Load and filter asv annotations.")

        self.asv_metadata_path = Path(self.config_env["ASV_CSV_METADATA_PATH"])
        if not self.asv_metadata_path.exists() or not self.asv_metadata_path.is_file():
            raise NameError(f"Orthophoto not found at path: {self.asv_metadata_path}")
        
        asv_metadata_df = pd.read_csv(self.asv_metadata_path)

        asv_metadata_gdf = gpd.GeoDataFrame(asv_metadata_df, geometry=gpd.points_from_xy(asv_metadata_df.GPSLongitude, asv_metadata_df.GPSLatitude, crs="EPSG:4326"))
        asv_metadata_gdf.to_crs(self.args.matching_crs, inplace=True)

        manual_boundary_path = Path(self.config_env["MANUEL_BOUNDARY_PATH"])
        if not manual_boundary_path.exists():
            raise NameError(f"Manual boundary file not found at path {manual_boundary_path}")

        polygon_df = gpd.read_file(manual_boundary_path)

        # Assuming there's only one polygon in the GeoJSON
        polygon = polygon_df.geometry.iloc[0]

        self.annotations_plancha_filtered = asv_metadata_gdf[asv_metadata_gdf.geometry.within(polygon)]

        self.annotations_plancha_filtered.to_file(Path(save_folder, "annotation_plancha_filtered.geojson"), driver='GeoJSON')
    

    def match_asv_annotations_with_tiles(self, save_folder: Path, tiles_bounds: pd.DataFrame) -> pd.DataFrame:
        print("\n\n-- func: Match asv annotations position with tiles bounds.")

        annotation_tiles = pd.DataFrame()
        for i, row in tqdm(tiles_bounds.iterrows(), total=len(tiles_bounds)):
            annotations_clipped = self.annotations_plancha_filtered[self.annotations_plancha_filtered.within(row["bounds_polygon"])].copy()
 
            if len(annotations_clipped) <= 0: continue

            annotations_clipped["PlanchaFileName"] = annotations_clipped.apply(lambda row: row["FileName"], axis=1)
            annotations_clipped["FileName"] = row["tile_png"]

            annotations_clipped["tile_bounds"] = row["bounds_polygon"]
            annotation_tiles = pd.concat([annotation_tiles, annotations_clipped])
        
        annotation_tiles = annotation_tiles.dropna(subset=['GPSRoll'])
        annotation_tiles = annotation_tiles.dropna(subset=['GPSPitch'])
        annotation_tiles = annotation_tiles.dropna(subset=['GPSTrack'])

        # annotation_tiles.to_csv(Path(save_folder, "annotation_tiles.csv"), index=False)

        return annotation_tiles