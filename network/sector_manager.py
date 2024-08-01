######################################################################################################################
# sector_manager.py inside the network folder and  SectorManager class is responsible for managing sectors            #
# within a network simulation environment. It centralizes the management of sectors, including their                  #
# initialization, updates, and the handling of User Equipment (UE) associations. This class follows the Singleton     # 
# design pattern to ensure that only one instance of the SectorManager exists throughout the application lifecycle    #
# SectorManager class can centralize the management of sectors, including their initialization, updates, and the      #
# handling of User Equipment (UE) associations. This approach can streamline interactions with the database and ensure#
# consistent state management across the application.                                                                 #
#######################################################################################################################
from network.sector import Sector, all_sectors
from database.database_manager import DatabaseManager
from influxdb_client import Point, WritePrecision
from logs.logger_config import cell_logger, gnodeb_logger, ue_logger, sector_logger
import threading

class SectorManager:
    _instance = None
    _lock = threading.Lock()
    _call_count = 0  # Add a class variable to count calls sector manager instance

    def __init__(self, db_manager):
        self.sectors = all_sectors  # Use the global all_sectors dictionary to track sectors
        self.db_manager = DatabaseManager.get_instance() # Instance of DatabaseManager for DB operations
        self.lock = threading.Lock()  # Lock for thread-safe operations on sectors
        self.gnodeb_sectors_map = {}  # New attribute to track gNodeB to sectors association
    
    @classmethod
    def get_instance(cls, db_manager=None):
        cls._call_count += 1
        sector_logger.debug(f"SectorManager get_instance called {cls._call_count} times.")
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_manager)
        return cls._instance
    
    def initialize_sectors(self, sectors_config, gnodeb_manager, cell_manager):
        print("Initializing sectors...")
        initialized_sectors = {}
        processed_sectors = set()

        for sector_data in sectors_config['sectors']:
            sector_id = sector_data['sector_id']
            cell_id = sector_data.get('cell_id')
            if not cell_id:
                print(f"Cell ID not provided for sector {sector_id}. Skipping.")
                continue

            cell = cell_manager.get_cell(cell_id)
            if not cell:
                print(f"Cell {cell_id} not found for sector {sector_id}. Skipping.")
                continue

            gnodeb_id = cell.gNodeB_ID
            if not gnodeb_manager.get_gNodeB(gnodeb_id):
                print(f"gNodeB {gnodeb_id} not initialized, cannot allocate sector {sector_id}.")
                continue

            sector_gnodeb_combo = (gnodeb_id, sector_id)
            if sector_gnodeb_combo in processed_sectors:
                print(f"Sector {sector_id} already processed for gNodeB {gnodeb_id}. Skipping.")
                continue

            processed_sectors.add(sector_gnodeb_combo)

            with self.lock:
                if sector_id not in self.sectors:
                    new_sector = Sector(
                        sector_id=sector_id,
                        cell_id=cell_id,
                        cell=cell,
                        capacity=sector_data['capacity'],
                        azimuth_angle=sector_data['azimuth_angle'],
                        beamwidth=sector_data['beamwidth'],
                        frequency=sector_data['frequency'],
                        duplex_mode=sector_data['duplex_mode'],
                        tx_power=sector_data['tx_power'],
                        bandwidth=sector_data['bandwidth'],
                        mimo_layers=sector_data['mimo_layers'],
                        beamforming=sector_data['beamforming'],
                        ho_margin=sector_data['ho_margin'],
                        load_balancing=sector_data['load_balancing'],
                        connected_ues=[],
                        max_throughput=sector_data['max_throughput'],
                        current_load=0
                    )
                    # Update the gNodeB to sectors mapping instead of calling gnodeb.add_sector
                    if gnodeb_id not in self.gnodeb_sectors_map:
                        self.gnodeb_sectors_map[gnodeb_id] = []
                    self.gnodeb_sectors_map[gnodeb_id].append(new_sector)

                    # Add sector to cell
                    cell.add_sector_to_cell(new_sector)

                    self.sectors[new_sector.sector_id] = new_sector
                    initialized_sectors[new_sector.sector_id] = new_sector
                    point = new_sector.serialize_for_influxdb()
                    self.db_manager.insert_data(point)
                    print(f"Sector {new_sector.sector_id} initialized and associated with gNodeB {gnodeb_id} and Cell {cell_id}.")
                else:
                    print(f"Sector {sector_id} already exists in the manager.")

        print("Sectors initialization completed.")
        return list(initialized_sectors.values()) #Return a list of Sector instances


    def remove_ue_from_sector(self, sector_id, ue_id):
        global global_ue_ids
        with self.lock:  # Assuming self.lock is accessible and used across both SectorManager and UEManager for shared resources
            sector = self.sectors.get(sector_id)
            if sector and ue_id in sector.connected_ues:
                print(f"Before removal, sector {sector_id} connected UEs: {sector.connected_ues}")
                sector.connected_ues.remove(ue_id)  # Correctly remove the ID string
                sector.current_load -= 1  # Decrement the current load
                global_ue_ids.discard(ue_id)  # Correctly discard the ID string
                sector.remaining_capacity = sector.capacity - len(sector.connected_ues)  # Update remaining_capacity
                if ue_id in sector.ues:  # Check if the UE is in the sector's UE dictionary before attempting to delete
                    del sector.ues[ue_id]  # Correctly delete the UE from the dictionary
                point = sector.serialize_for_influxdb()
                self.db_manager.insert_data(point)  # Use SectorManager's db_manager to insert data
                print(f"After removal, sector {sector_id} connected UEs: {sector.connected_ues}")
                sector_logger.info(f"UE with ID {ue_id} has been removed from the sector {sector_id}. Current load: {sector.current_load}")
                return True  # Return True to indicate successful removal
            else:
                sector_logger.warning(f"UE with ID {ue_id} is not connected to the sector {sector_id}.")
                return False  # Return False to indicate failure or that the UE was not found in the sector

    def update_sector(self, sector_id, updates):
        """
        Updates properties of a specified sector.
        :param sector_id: ID of the sector to update.
        :param updates: Dictionary containing updates (property: new_value).
        """
        with self.lock:
            sector = self.sectors.get(sector_id)
            if sector:
                for key, value in updates.items():
                    if hasattr(sector, key):
                        setattr(sector, key, value)
                        sector_logger.info(f"Sector {sector_id} property {key} updated to {value}.")
                    else:
                        sector_logger.warning(f"Sector {sector_id} has no property {key}.")
                # Serialize and update the sector in the database
                point = sector.serialize_for_influxdb()
                self.db_manager.insert_data(point)
            else:
                sector_logger.warning(f"Sector {sector_id} not found.")

    def get_sector_state(self, sector_id):
        """
        Queries the database for the current state of a sector.
    
        :param sector_id: ID of the sector to query.
        :return: Sector state or None if not found.
        """
        sector_state = self.db_manager.query_sector_state(sector_id)
        if sector_state:
            sector_logger.info(f"State retrieved for sector {sector_id}.")
        else:
            sector_logger.warning(f"Sector state not found for {sector_id}.")
        return sector_state
    
    def get_neighbor_sectors(self, sector_id):
        """
        Finds neighboring sectors for a given sector ID.
    
        :param sector_id: The ID of the sector for which to find neighbors.
        :return: A list of Sector instances that are considered neighbors.
        """
        current_sector = self.sectors.get(sector_id)
        if not current_sector:
            sector_logger.warning(f"Sector {sector_id} not found.")
            return []

        neighbors = []
        # Example criteria: Sectors are neighbors if they belong to the same gNodeB.
        for sector in self.sectors.values():
            if sector.gNodeB_ID == current_sector.gNodeB_ID and sector.sector_id != sector_id:
                neighbors.append(sector)
    
        return neighbors
    
    def is_sector_overloaded(self, sector_id):
        sector = self.sector_manager.get_sector(sector_id)
        if sector and sector.current_load > 80:  # Assuming 80% is the threshold
            return True
        return False
    
    def get_sorted_ues_by_throughput(self, sector_id):
        sector = self.sector_manager.get_sector(sector_id)
        if not sector:
            return []
        sorted_ues = sorted(sector.ues.values(), key=lambda ue: ue.throughput, reverse=True)
        return sorted_ues
    
    def find_sector_by_ue_id(self, ue_id):
        # Assuming UE IDs are expected to be strings in connected_ues
        # Convert ue_id to string if it's not already
        ue_id_str = str(ue_id)

        for sector_id, sector in self.sectors.items():
            # Ensure connected_ues contains strings for comparison
            if ue_id_str in map(str, sector.connected_ues):
                return sector_id
        return None
    
    def get_sector_by_id(self, sector_id):
    # Assuming self.sectors is a dictionary mapping sector IDs to Sector objects
        return self.sectors.get(sector_id)
    def list_all_sectors(self):
        """
        Lists all sectors managed by the SectorManager.

        :return: A list of dictionaries, each representing a sector with its details.
        """
        with self.lock:  
            sector_list = []
            for sector_id, sector in self.sectors.items():
                sector_details = {
                    "sector_id": sector.sector_id,
                    "cell_id": sector.cell_id,
                    "capacity": sector.capacity,
                    "current_load": sector.current_load,
                    "max_throughput": sector.max_throughput,
                    # Add more details as needed
                }
                sector_list.append(sector_details)
            return sector_list
        
        