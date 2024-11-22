import shutil
from pathlib import Path
from argparse import Namespace, ArgumentParser

from src.utils.Orthophoto import Orthophoto
from src.utils.ASVManager import ASVManager
from src.utils.AnnotationMaker import AnnotationMaker

def parse_args() -> Namespace:
    parser = ArgumentParser(description="Split UAV orthophoto to tiles and upscale ASV predictions to UAV annotations.")

    # Default parameters
    parser.add_argument('-crs', '--matching_crs', type=str, default="32740", help="Default CRS of the project.")
    parser.add_argument('-tsm', '--tiles_size_meters', type=float, default=1.5, help='Tile size in meters')
    parser.add_argument('-ft', '--footprint_threshold', type=float, default=1.0, help='Footprint threshold to keep image. Default: Keep tiles with 100% coverage')
    parser.add_argument('--fov_x', type=float, default=94.4, help='ASV Vamera FOV X')
    parser.add_argument('--fov_y', type=float, default=122.6, help='ASV Vamera FOV Y')
    parser.add_argument('-hs', '--h_shift', type=float, default=0, help='Horizontal overlap. Default 0')
    parser.add_argument('-vs', '--v_shift', type=float, default=0, help='Vertical overlap.')
    parser.add_argument('-bptp', '--black_pixels_threshold_percentage', type=float, default=5, help="Don't keep tile if we have a bigger percentage of black pixels than threshold.")
    parser.add_argument('-wptp', '--white_pixels_threshold_percentage', type=float, default=5, help="Don't keep tile if we have a bigger percentage of white pixels than threshold.")


    # Global options.
    parser.add_argument('--config_path', default="config/config_stleu.json", help="Path to config.json file.")
    parser.add_argument('-c', '--clear_all', action="store_true", help="Clear all processed data.")

    return parser.parse_args()


def main(args: Namespace) -> None:


    # Setup.
    orthoManager = Orthophoto(args)
    asvManager = ASVManager(args)
    annotationMaker = AnnotationMaker()

    # Create output folder.
    print("Init output folder.")
    output_folder = Path(orthoManager.config_env["OUTPUT_DIR_PATH"])
    if output_folder.exists() and args.clear_all:
        shutil.rmtree(output_folder)
    output_folder.mkdir(exist_ok=True, parents=True)

    # Create tiles_folder for tif.
    tiles_folder_name = "drone_tiles" 
    if args.h_shift != 0 and args.v_shift != 0:
        tiles_folder_name = f"{tiles_folder_name}_overlap{args.h_shift}"
    if args.footprint_threshold != 1.0:
        tiles_folder_name = f"{tiles_folder_name}_footprint{args.footprint_threshold}"

    tiles_folder = Path(output_folder, tiles_folder_name)
    tiles_folder.mkdir(exist_ok=True, parents=True)

    # Create tiles_folder for png.
    tiles_png_folder = Path(output_folder, f"{tiles_folder_name}_png")
    tiles_png_folder.mkdir(exist_ok=True, parents=True)

    # Split tif into tiles and filter on manual boundary
    tiles_bounds_df = orthoManager.setup_ortho_tiles(output_folder, tiles_folder, tiles_png_folder)

    annotation_filtered_gdf = asvManager.compute_annotations(output_folder, tiles_bounds_df)

    unlabeled_folder = annotationMaker.create_and_compute_annotations(output_folder, tiles_png_folder, annotation_filtered_gdf)

    orthoManager.create_unlabeled_csv(output_folder, unlabeled_folder, tiles_bounds_df)

if __name__ == "__main__":
    args = parse_args()
    main(args)
