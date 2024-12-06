import shutil
from pathlib import Path
from argparse import Namespace


from ..utils.tools import get_config_env

class BaseManager:

    needSetup = True
    def __init__(self, args: Namespace) -> None:

        self.args = args
        self.config_env = get_config_env(self.args.config_path)
        
        self.base_setup()
    
    # Warning Call this function only one time
    def base_setup(self) -> None:

        self.output_folder = Path(self.config_env["OUTPUT_DIR_PATH"])
        if BaseManager.needSetup and self.output_folder.exists() and self.args.clear_all:
            shutil.rmtree(self.output_folder)
        self.output_folder.mkdir(exist_ok=True, parents=True)

        # Create tiles_folder for tif.
        tiles_folder_name = "drone_tiles" 
        if self.args.h_shift != 0 and self.args.v_shift != 0:
            tiles_folder_name = f"{tiles_folder_name}_overlap{self.args.h_shift}"
        if self.args.footprint_threshold != 1.0:
            tiles_folder_name = f"{tiles_folder_name}_footprint{self.args.footprint_threshold}"

        self.tiles_folder = Path(self.output_folder, tiles_folder_name)
        self.tiles_folder.mkdir(exist_ok=True, parents=True)

        # Create tiles_folder for png.
        self.tiles_png_folder = Path(self.output_folder, f"{tiles_folder_name}_png")
        self.tiles_png_folder.mkdir(exist_ok=True, parents=True)

        BaseManager.needSetup = False
