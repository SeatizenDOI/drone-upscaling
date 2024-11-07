import shutil
from pathlib import Path
from argparse import Namespace, ArgumentParser

from src.ortho.Orthophoto import Orthophoto

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

    # Create output folder.
    print("Init output folder.")
    output_folder = Path(orthoManager.config_env["OUTPUT_DIR_PATH"])
    if output_folder.exists() and args.clear_all:
        shutil.rmtree(output_folder)
    output_folder.mkdir(exist_ok=True, parents=True)

    # Create tiles_folder.
    tiles_folder_name = "drone_tiles" if args.h_shift == 0 and args.v_shift == 0 else f"drone_tiles_overlap{args.h_shift}"
    tiles_folder = Path(output_folder, tiles_folder_name)
    tiles_folder.mkdir(exist_ok=True, parents=True)

    tiles_png_folder = Path(output_folder, "drone_tiles_png")
    tiles_png_folder.mkdir(exist_ok=True, parents=True)

    # Split tif into tiles and filter on manual boundary
    orthoManager.setup_ortho_tiles(tiles_folder, tiles_png_folder)



if __name__ == "__main__":
    args = parse_args()
    main(args)