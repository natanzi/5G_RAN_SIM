import os
import json
import sys

class Config:
    _instance = None

    @classmethod
    def get_instance(cls, base_dir=None):
        if cls._instance is None:
            cls._instance = cls(base_dir)
        return cls._instance

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = self.determine_base_dir()
        
        self.base_dir = base_dir
        self.config_dir = os.path.join(self.base_dir, 'Config_files')
        
        if not os.path.exists(self.config_dir):
            raise FileNotFoundError(f"Config_files directory not found at {self.config_dir}")

        self.gNodeBs_config = self.load_json_config('gNodeB_config.json')
        self.cells_config = self.load_json_config('cell_config.json')
        self.sectors_config = self.load_json_config('sector_config.json')
        self.ue_config = self.load_json_config('ue_config.json')
        self.network_map_data = self.load_or_generate_network_map()

    def determine_base_dir(self):
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle
            return os.path.dirname(sys.executable)
        else:
            # If run from a script
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def load_json_config(self, filename):
        file_path = os.path.join(self.config_dir, filename)
        print(f"Attempting to load config from: {file_path}")  # Debug print
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"Config file not found: {file_path}")
            return {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from file: {file_path}")
            return {}

    def load_or_generate_network_map(self):
        network_map_path = os.path.join(self.config_dir, 'network_map.json')
        if os.path.exists(network_map_path):
            return self.load_json_config('network_map.json')
        else:
            return self.generate_and_save_network_map()

    def generate_and_save_network_map(self):
        # ... (keep your existing implementation)
        pass

    @property
    def base_directory(self):
        return self.base_dir

    @property
    def config_directory(self):
        return self.config_dir