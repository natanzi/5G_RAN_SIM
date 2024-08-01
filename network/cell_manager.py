#############################################################################################################
# cell_manager.py inside the network folder.The CellManager class is responsible for managing Cell instances#
# within the network simulation. It oversees the creation, update, deletion, and overall management of cells#
# across the network. This class employs the Singleton design pattern to ensure that only one instance of   #
# CellManager exists throughout the application lifecycle, thus centralizing cell management.               #
#                                                                                                           #
#############################################################################################################
import os
import threading
# Removed the incorrect import statement
from logs.logger_config import cell_logger
import json
from database.database_manager import DatabaseManager
from network.cell import Cell 

class CellManager:
    _instance = None
    _lock = threading.Lock()
    _call_count = 0  # Add a class variable to count calls

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(CellManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls, gNodeBs=None, db_manager=None):
        print(f"get_instance called with gNodeBs: {gNodeBs}, db_manager: {db_manager}")
        cls._call_count += 1
        cell_logger.debug(f"CellManager get_instance called {cls._call_count} times.")
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(gNodeBs, db_manager)  # Pass both arguments here
        return cls._instance
    
    def __init__(self, gNodeBs, db_manager):
        if not hasattr(self, 'initialized'):  # This ensures __init__ is only called once
            print(f"Creating CellManager instance: {self}")
            self.cells = {}
            self.gNodeBs = gNodeBs
            self.db_manager = db_manager  # Use the provided db_manager instance
            self.initialized = True
            
    def initialize_cells(self, cells_config):
        
        if self.cells:  # Check if cells already initialized
            print("Cells already initialized.")
            return
        """
        Initialize cells based on the provided configuration and associate them with gNodeBs.
        
        :param cells_config: Configuration data for cells.
        :return: Dictionary of initialized cells.
        """
        if self.gNodeBs is None:
            cell_logger.error("gNodeBs is None. Cannot initialize cells.")
            return None  # Ensure to return None or an appropriate value indicating failure

        cell_logger.info("Initializing cells.")
        for cell_data in cells_config['cells']:
            cell_id = cell_data['cell_id']
            gNodeB_id = cell_data['gnodeb_id']
            if gNodeB_id not in self.gNodeBs:
                cell_logger.error(f"Error: gNodeB {gNodeB_id} not found for cell {cell_id}")
                continue

            new_cell = Cell(**cell_data)
            # Placeholder for cell load calculation
            # Replace this with actual cell load calculation logic
            cell_load = 0.5  # This is a placeholder value

            # Add the cell to the corresponding gNodeB
            if gNodeB_id in self.gNodeBs:
                self.gNodeBs[gNodeB_id].add_cell_to_gNodeB(new_cell)

            # Add the new cell to the cells dictionary
            self.cells[cell_id] = new_cell

            # Serialize for InfluxDB and insert data
            point = new_cell.serialize_for_influxdb(cell_load)
            self.db_manager.insert_data(point)

        cell_logger.info("Cells initialization completed.")
        #print(f"Initialized cells print for test the issue: {self.cells}")  # Add this line to print out the cells
        return self.cells  # Return the dictionary of initialized cells

    def add_cell(self, cell_data):
        """
        Add a single cell instance to the manager and associate it with a gNodeB.

        :param cell_data: Dictionary containing the data for the cell to be added.
        """
        cell_id = cell_data['cell_id']
        gNodeB_id = cell_data['gnodeb_id']
        if cell_id in self.cells:
            cell_logger.error(f"Duplicate cell ID {cell_id} found.")
            raise ValueError(f"Duplicate cell ID {cell_id} found.")

        if gNodeB_id not in self.gNodeBs:
            cell_logger.error(f"gNodeB {gNodeB_id} not found.")
            raise ValueError(f"gNodeB {gNodeB_id} not found.")

        new_cell = Cell(**cell_data)
        self.gNodeBs[gNodeB_id].add_cell_to_gNodeB(new_cell)  # Associate the cell with a gNodeB
        self.cells[cell_id] = new_cell  # Add the new cell to the CellManager's dictionary of cells

        # Assuming the Cell class has an update_ue_lists method
        new_cell.update_ue_lists()  # Update the UE lists of the newly added cell

        point = new_cell.serialize_for_influxdb()  # Serialize the cell for InfluxDB
        self.db_manager.insert_data(point)  # Insert the serialized data into the database

    def remove_cell(self, cell_id):
        """
        Remove a cell instance from the manager.

        :param cell_id: ID of the cell to be removed.
        """
        if cell_id in self.cells:
            # Retrieve the cell to be removed
            cell_to_remove = self.cells[cell_id]

            # Optional: Notify other parts of the system about the cell removal
            # This could include updating UE lists in neighboring cells, if applicable
            # For example:
            # self.notify_cell_removal(cell_to_remove)

            # Remove the cell from its associated gNodeB
            # Assuming each cell knows its gNodeB_id or can retrieve it
            gNodeB_id = cell_to_remove.gNodeB_id  # This is an example; actual implementation may vary
            if gNodeB_id in self.gNodeBs:
                self.gNodeBs[gNodeB_id].remove_cell_from_gNodeB(cell_id)

            # Remove the cell from the CellManager's dictionary of cells
            del self.cells[cell_id]

            # Remove cell data from the database
            self.db_manager.remove_data(cell_id)  # Ensure you have this method in your DBManager

            cell_logger.info(f"Cell ID {cell_id} removed.")
        else:
            cell_logger.error(f"Cell ID {cell_id} not found.")

    def get_cell(self, cell_id):
        """
        Retrieve a cell instance by its ID.
        
        :param cell_id: ID of the cell to retrieve.
        :return: The cell instance, if found; None otherwise.
        """
        return self.cells.get(cell_id)
    
    def get_neighbor_cells(gNodeB, target_cell_id):
        """
        Finds neighboring cells of a given cell within the same gNodeB.

        :param gNodeB: The gNodeB instance containing the target cell.
        :param target_cell_id: The ID of the cell for which to find neighbors.
        :return: A list of cell IDs that are neighbors of the target cell.
        """
        neighbor_cells = []
        # Check if the target cell is part of this gNodeB
        if target_cell_id not in gNodeB.CellIds:
            print(f"Cell ID {target_cell_id} not found in gNodeB {gNodeB.ID}")
            return neighbor_cells  # Return an empty list if the target cell is not in this gNodeB

        # Iterate over all cells in the gNodeB to find neighbors
        for cell in gNodeB.Cells:
            if cell.ID != target_cell_id:
                neighbor_cells.append(cell.ID)

        return neighbor_cells
    
    def list_all_cells_detailed(self):
        cell_details_list = []
        for cell_id, cell in self.cells.items():
            cell_details_list.append({
                'id': cell.ID,
                # Add more details as needed
            })
        return cell_details_list