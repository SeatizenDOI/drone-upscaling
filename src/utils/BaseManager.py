from argparse import Namespace

from ..utils.tools import get_config_env

class BaseManager:

    def __init__(self, args: Namespace) -> None:

        self.args = args
        self.config_env = get_config_env(self.args.config_path)