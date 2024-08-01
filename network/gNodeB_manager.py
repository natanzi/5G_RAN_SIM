###################################################################################################################
# gNodeBManager.py inside the network folder .#The gNodeBManager class is responsible for managing gNodeB (gNB)   #
# instances within the network simulation. It provides functionalities to create, update, delete, and manage gNBs #
# across the network. This class follows the Singleton design pattern to ensure that only one instance of the     #
# gNodeBManager exists throughout the application lifecycle.                                                      #
###################################################################################################################
import os
from network.gNodeB import gNodeB, load_gNodeB_config
from database.database_manager import DatabaseManager
from logs.logger_config import cell_logger, gnodeb_logger
from network.utils import calculate_distance
import threading

class gNodeBManager:
    _instance = None
    _lock = threading.Lock()
    _call_count = 0  # Add a class variable to count calls

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(gNodeBManager, cls).__new__(cls)
            # Initialize the object here, if necessary
        return cls._instance
    
    @classmethod
    def get_instance(cls, db_manager=None):
        cls._call_count += 1
        gnodeb_logger.debug(f"gNodeBManager get_instance called {cls._call_count} times.")
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_manager)
        return cls._instance
    
    def __init__(self, base_dir):
        if not hasattr(self, 'initialized'):
            self.gNodeBs = {}
            self.db_manager = DatabaseManager.get_instance()
            self.base_dir = base_dir
            self.gNodeBs_config = load_gNodeB_config()

        # Check if gNodeBs_config contains gNodeBs data
        if 'gNodeBs' not in self.gNodeBs_config or not self.gNodeBs_config['gNodeBs']:
            gnodeb_logger.error("gNodeBs configuration is missing or empty.")
            raise ValueError("gNodeBs configuration is missing or empty.")
        self.initialized = True

    def initialize_gNodeBs(self):
        """
        Initialize gNodeBs based on the loaded configuration and insert them into the database.
        """
        for gNodeB_data in self.gNodeBs_config['gNodeBs']:
            if gNodeB_data['gnodeb_id'] in self.gNodeBs:
                raise ValueError(f"Duplicate gNodeB ID {gNodeB_data['gnodeb_id']} found during initialization.")
            
            gnodeb = gNodeB(**gNodeB_data)
            self.gNodeBs[gnodeb.ID] = gnodeb
            point = gnodeb.serialize_for_influxdb()  # Serialize for InfluxDB
            self.db_manager.insert_data(point)  # Insert the Point object directly
        return self.gNodeBs
    
    def list_all_gNodeBs_detailed(self):
        """List all gNodeBs managed by this manager with detailed information."""
        gNodeBs_detailed_list = []
        for gnodeb_id, gnodeb in self.gNodeBs.items():
            gNodeBs_detailed_list.append({
                'id': gnodeb.ID,
                'latitude': gnodeb.Latitude,
                'longitude': gnodeb.Longitude,
                'coverage_radius': gnodeb.CoverageRadius,
                'transmission_power': gnodeb.TransmissionPower,
                'frequency': gnodeb.Frequency,
                'bandwidth': gnodeb.Bandwidth,
                'max_ues': gnodeb.MaxUEs,
                'cell_count': gnodeb.CellCount,
                'sector_count': gnodeb.SectorCount,
                # Add more fields as needed
            })
        return gNodeBs_detailed_list

    def add_gNodeB(self, gNodeB_data):
        """
        Add a single gNodeB instance to the manager and the database.
        
        :param gNodeB_data: Dictionary containing the data for the gNodeB to be added.
        """
        if gNodeB_data['gnodeb_id'] in self.gNodeBs:
            raise ValueError(f"Duplicate gNodeB ID {gNodeB_data['gnodeb_id']} found.")
        
        gnodeb = gNodeB(**gNodeB_data)
        self.gNodeBs[gnodeb.ID] = gnodeb
        point = gnodeb.serialize_for_influxdb()
        self.db_manager.insert_data(point)

    def remove_gNodeB(self, gnodeb_id):
        """
        Remove a gNodeB instance from the manager and the database.
        
        :param gnodeb_id: ID of the gNodeB to be removed.
        """
        if gnodeb_id in self.gNodeBs:
            del self.gNodeBs[gnodeb_id]
            # Assuming there's a method in DBManager to remove data
            self.db_manager.remove_data(gnodeb_id)
        else:
            print(f"gNodeB ID {gnodeb_id} not found.")

    def get_gNodeB(self, gnodeb_id):
        """
        Retrieve a gNodeB instance by its ID.
        
        :param gnodeb_id: ID of the gNodeB to retrieve.
        :return: The gNodeB instance, if found; None otherwise.
        """
        return self.gNodeBs.get(gnodeb_id)
    
        
    def get_neighbor_gNodeBs(self, gnodeb_id):
        """
        Find neighboring gNodeBs based on coverage radius overlap.

        :param gnodeb_id: ID of the gNodeB to find neighbors for.
        :return: A list of gNodeB IDs that are neighbors based on coverage overlap.
        """
        target_gNodeB = self.get_gNodeB(gnodeb_id)
        if not target_gNodeB:
            return []  # Target gNodeB not found

        neighbors = []
        for gnb_id, gnb in self.gNodeBs.items():
            if gnb_id != gnodeb_id:  # Don't include the target gNodeB itself
                distance = calculate_distance(target_gNodeB.Latitude, target_gNodeB.Longitude, gnb.Latitude, gnb.Longitude)
                # Check if the distance is less than the sum of their coverage radii
                if distance <= (target_gNodeB.CoverageRadius + gnb.CoverageRadius) / 1000:  # Convert meters to kilometers
                    neighbors.append(gnb_id)

        return neighbors