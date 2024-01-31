# This is the config.py in Config_files directory to load all JSON configs
#Creating a Config class to encapsulate the different configuration dictionaries

import os
import json

class Config:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.gNodeBs_config = self.load_json_config('gNodeB_config.json')
        self.cells_config = self.load_json_config('cell_config.json')
        self.sectors_config = self.load_json_config('sector_config.json')
        self.ue_config = self.load_json_config('ue_config.json')
        self.network_map = self.load_or_generate_network_map()

    def load_json_config(self, filename):
        file_path = os.path.join(self.base_dir, 'Config_files', filename)
        with open(file_path, 'r') as file:
            return json.load(file)
        
    def load_or_generate_network_map(self):
        network_map_path = os.path.join(self.base_dir, 'Config_files', 'network_map.json')
        if os.path.exists(network_map_path):
            with open(network_map_path, 'r') as file:
                return json.load(file)
        else:
            return self.generate_network_map()
        
    def network_map(self):
        network_map = {
            "gNodeBs": []
        }
        for gnodeb in self.gNodeBs_config['gNodeBs']:
            gnodeb_entry = {
                "gNodeBId": gnodeb['gnodeb_id'],
                "cells": []
            }
            associated_cells = [cell for cell in self.cells_config['cells'] if cell['gnodeb_id'] == gnodeb['gnodeb_id']]
            for cell in associated_cells:
                # List sectors for this cell
                sectors_for_cell = [{"sectorId": sector['sector_id']} 
                                    for sector in self.sectors_config['sectors'] 
                                    if sector['cell_id'] == cell['cell_id']]
            
                cell_entry = {
                    "cellId": cell['cell_id'],
                    "sectors": sectors_for_cell
                }
                gnodeb_entry["cells"].append(cell_entry)
            network_map["gNodeBs"].append(gnodeb_entry)
    
        # Save the network map to a JSON file in the Config_files directory
        output_file_path = os.path.join(self.base_dir, 'Config_files', 'network_map.json')
        with open(output_file_path, 'w') as file:
            json.dump(network_map, file, indent=2)



