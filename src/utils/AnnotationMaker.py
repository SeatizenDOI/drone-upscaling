import shutil
import pandas as pd
from tqdm import tqdm
import geopandas as gpd
from pathlib import Path
from pyproj import Transformer

from .tools import calculate_probability_from_binary_fine_scale, calculate_probability_from_probs_fine_scale

class AnnotationMaker():

    def create_and_compute_annotations(self, save_folder: Path, drone_folder_png: Path, annotation_tiles_gdf_filtered: gpd.GeoDataFrame) -> Path: 

        binary_annotation_df = self.create_binary_annotations_for_tiles(annotation_tiles_gdf_filtered)
        annotations_tiles_from_binary_fine_scale = self.create_probability_annotations_for_tiles(save_folder, annotation_tiles_gdf_filtered, binary_annotation_df)
        unlabeled_folder = self.move_images_by_annotations(save_folder, drone_folder_png, annotations_tiles_from_binary_fine_scale)
        return unlabeled_folder
    

    def move_images_by_annotations(self, save_folder: Path, drone_folder_png: Path, df_anno) -> Path:
        print("\n\n-- func: Copy images into annotated and unlabeled folder.")
        
        annotated_dir = Path(save_folder, 'annotated_images_png')
        annotated_dir.mkdir(exist_ok=True, parents=True)

        unlabeled_dir = Path(save_folder, "unlabeled_images_png")
        unlabeled_dir.mkdir(exist_ok=True, parents=True)

        df_anno.set_index("FileName", inplace=True)

        for file_png in tqdm(drone_folder_png.iterdir()):
            if not file_png.is_file() or file_png.suffix.lower() != ".png": continue

            output_path = Path(annotated_dir, file_png.name) if file_png.name in df_anno.index else Path(unlabeled_dir, file_png.name)

            shutil.move(file_png, output_path)

        drone_folder_png.rmdir()
        return unlabeled_dir


    def create_binary_annotations_for_tiles(self, annotation_tiles_gdf_filtered: gpd.GeoDataFrame):
        print("\n\n-- func: Create binary annotations.")
        # https://huggingface.co/lombardata/DinoVdeau-large-2024_04_03-with_data_aug_batch-size32_epochs150_freeze/blob/main/threshold.json
        threshold_classes = {"Acropore_branched": 0.351, "Acropore_digitised": 0.349, "Acropore_sub_massive": 0.123, "Acropore_tabular": 0.415, "Algae_assembly": 0.434, "Algae_drawn_up": 0.193, "Algae_limestone": 0.346, "Algae_sodding": 0.41, "Atra/Leucospilota": 0.586, "Bleached_coral": 0.408, "Blurred": 0.3, "Dead_coral": 0.407, "Fish": 0.466, "Homo_sapiens": 0.402, "Human_object": 0.343, "Living_coral": 0.208, "Millepore": 0.292, "No_acropore_encrusting": 0.227, "No_acropore_foliaceous": 0.462, "No_acropore_massive": 0.333, "No_acropore_solitary": 0.415, "No_acropore_sub_massive": 0.377, "Rock": 0.476, "Sand": 0.548, "Rubble": 0.417, "Sea_cucumber": 0.357, "Sea_urchins": 0.335, "Sponge": 0.152, "Syringodium_isoetifolium": 0.476, "Thalassodendron_ciliatum": 0.209, "Useless": 0.315}

        # create a dataframe like annotation_tiles_gdf_filtered but with binary values (True, False) based on threshold_classes
        binary_annotation_df = annotation_tiles_gdf_filtered.copy()
        for class_name, threshold in threshold_classes.items():
            binary_annotation_df[class_name] = binary_annotation_df[class_name] > threshold

        class_columns = []

        # define class columns, all columns except FileName, 'SubSecDateTimeOriginal','GPSTrack', 'GPSRoll', 'GPSPitch', 'GPSAltitude', 'GPSLatitude','GPSLongitude', 'geometry', 'PlanchaFileName', 'tile_bounds','UnderwaterImageFootprint', 'Intersection', 'TileArea','UnderwaterImageArea', 'IntersectionArea',
        class_columns = [col for col in binary_annotation_df.columns if col not in ['FileName', 'SubSecDateTimeOriginal','GPSTrack', 'GPSRoll', 'GPSPitch', 'GPSAltitude', 'GPSLatitude','GPSLongitude', 'geometry', 'PlanchaFileName', 'tile_bounds','UnderwaterImageFootprint', 'Intersection', 'TileArea','UnderwaterImageArea', 'IntersectionArea']]
        # Define the algae columns
        algae_columns = ['Algae_assembly', 'Algae_limestone', 'Algae_sodding', 'Algae_drawn_up']
        # Create the new Algae column
        binary_annotation_df['Algae'] = binary_annotation_df[algae_columns].any(axis=1)
        for algae_class in algae_columns :
            if algae_class in class_columns :
                class_columns.remove(algae_class)
        class_columns.append('Algae')

        binary_annotation_df = binary_annotation_df.drop(columns=algae_columns)

        return binary_annotation_df
    

    def create_probability_annotations_for_tiles(self, save_folder: Path, annotation_tiles_gdf_filtered: gpd.GeoDataFrame, binary_annotation_df):
        print("\n\n-- func: Create probability annotations.")
        
        classes = []
        # define class columns, all columns except FileName, 'SubSecDateTimeOriginal','GPSTrack', 'GPSRoll', 'GPSPitch', 'GPSAltitude', 'GPSLatitude','GPSLongitude', 'geometry', 'PlanchaFileName', 'tile_bounds','UnderwaterImageFootprint', 'Intersection', 'TileArea','UnderwaterImageArea', 'IntersectionArea',
        classes = [col for col in annotation_tiles_gdf_filtered.columns if col not in ['FileName', 'SubSecDateTimeOriginal','GPSTrack', 'GPSRoll', 'GPSPitch', 'GPSAltitude', 'GPSLatitude','GPSLongitude', 'geometry', 'PlanchaFileName', 'tile_bounds','UnderwaterImageFootprint', 'Intersection', 'TileArea','UnderwaterImageArea', 'IntersectionArea']]
        # Define the algae columns
        algae_columns = ['Algae_assembly', 'Algae_limestone', 'Algae_sodding', 'Algae_drawn_up']
        # Create the new Algae column
        annotation_tiles_gdf_filtered['Algae'] = annotation_tiles_gdf_filtered[algae_columns].max(axis=1)
        for algae_class in algae_columns :
            if algae_class in classes :
                classes.remove(algae_class)
        classes.append('Algae')

        # Print the identified classes to debug
        print("Identified classes:", classes)

        # Create a new DataFrame to store the results
        annotations_tiles_from_binary_fine_scale = pd.DataFrame(columns=['FileName'] + classes)
        annotations_tiles_from_probs_fine_scale = pd.DataFrame(columns=['FileName'] + classes)

        # Compute tiles annotations based on binary fine scale predictions
        for file_name, group in binary_annotation_df.groupby('FileName'):
            probabilities = {class_name: calculate_probability_from_binary_fine_scale(group, class_name) for class_name in classes}
            probabilities['FileName'] = file_name
            probabilities['GPSLatitude'] = group['GPSLatitude'].iloc[0]
            probabilities['GPSLongitude'] = group['GPSLongitude'].iloc[0]
            annotations_tiles_from_binary_fine_scale = pd.concat([annotations_tiles_from_binary_fine_scale, pd.DataFrame([probabilities])], ignore_index=True)
     
        # clean probabilities dict
        probabilities = {class_name: 0.0 for class_name in classes}

        # Compute tiles annotations based on probability fine scale predictions
        for file_name, group in annotation_tiles_gdf_filtered.groupby('FileName'):
            probabilities = {class_name: calculate_probability_from_probs_fine_scale(group, class_name) for class_name in classes}
            probabilities['FileName'] = file_name
            probabilities['GPSLatitude'] = group['GPSLatitude'].iloc[0]
            probabilities['GPSLongitude'] = group['GPSLongitude'].iloc[0]
            annotations_tiles_from_probs_fine_scale = pd.concat([annotations_tiles_from_probs_fine_scale, pd.DataFrame([probabilities])], ignore_index=True)
    
        # order class columns by alphabetic order in annotations_tiles_from_probs_fine_scale
        annotations_tiles_from_probs_fine_scale = annotations_tiles_from_probs_fine_scale[['FileName', 'GPSLatitude', 'GPSLongitude'] + sorted(classes)]
        annotations_tiles_from_binary_fine_scale = annotations_tiles_from_binary_fine_scale[['FileName', 'GPSLatitude', 'GPSLongitude'] + sorted(classes)]

        # Calculate centroids for each FileName
        centroids = annotation_tiles_gdf_filtered.dissolve(by='FileName').centroid
        # Create a DataFrame from centroids with latitude and longitude extracted
        centroids_df = centroids.to_frame(name='geometry').reset_index()
        centroids_df['GPSLatitude'] = centroids_df['geometry'].y
        centroids_df['GPSLongitude'] = centroids_df['geometry'].x

        #columns_to_drop = ["GPSTrack", "GPSRoll", "GPSPitch", 'GPSLatitude', 'GPSLongitude', 'geometry', 'PlanchaFileName', 'tile_bounds', 'TileArea', 'UnderwaterImageFootprint', 'UnderwaterImageArea', 'IntersectionArea', 'Intersection']
        columns_to_drop = ['GPSLatitude', 'GPSLongitude']
        annotations_tiles_from_probs_fine_scale = annotations_tiles_from_probs_fine_scale.drop(columns=columns_to_drop)
        annotations_tiles_from_binary_fine_scale = annotations_tiles_from_binary_fine_scale.drop(columns=columns_to_drop)

        # Merging centroid information
        annotations_tiles_from_probs_fine_scale = pd.merge(annotations_tiles_from_probs_fine_scale, centroids_df[['FileName', 'GPSLatitude', 'GPSLongitude']], on='FileName', how='left')
        annotations_tiles_from_binary_fine_scale = pd.merge(annotations_tiles_from_binary_fine_scale, centroids_df[['FileName', 'GPSLatitude', 'GPSLongitude']], on='FileName', how='left')

        # Initialize a Transformer object for converting UTM Zone 40S (EPSG:32740) to WGS84
        transformer = Transformer.from_crs("epsg:32740", "epsg:4326", always_xy=True)

        def utm_to_wgs84(row):
            lon, lat = transformer.transform(row['GPSLongitude'], row['GPSLatitude'])
            return pd.Series([lat, lon])

        # Apply the conversion to each row in the DataFrame
        annotations_tiles_from_probs_fine_scale[['GPSLatitude', 'GPSLongitude']] = annotations_tiles_from_probs_fine_scale.apply(utm_to_wgs84, axis=1)
        annotations_tiles_from_binary_fine_scale[['GPSLatitude', 'GPSLongitude']] = annotations_tiles_from_binary_fine_scale.apply(utm_to_wgs84, axis=1)

        annotations_tiles_from_probs_fine_scale_path = Path(save_folder, "annotations_tiles_from_probs_fine_scale.csv")
        annotations_tiles_from_binary_fine_scale_path = Path(save_folder, "annotations_tiles_from_binary_fine_scale.csv")
        annotations_tiles_from_probs_fine_scale.to_csv(annotations_tiles_from_probs_fine_scale_path, index=False)
        annotations_tiles_from_binary_fine_scale.to_csv(annotations_tiles_from_binary_fine_scale_path, index=False)

        return annotations_tiles_from_binary_fine_scale