###################################################################################################################################
# initialize_network.py is located in network directory and is responsible for Initialization of gNodeBs, Cells, sectors, and UEs # 
# in the the network simulation environment. It sets up gNodeBs, Cells, Sectors, and UEs (User Equipments) based on the           #
# configuration provided. This script is a crucial part of the network simulation setup, ensuring that all network components are #
# correctly initialized and ready for simulation.                                                                                 #
###################################################################################################################################
from network.gNodeB_manager import gNodeBManager
from network.cell_manager import CellManager
from network.sector_manager import SectorManager
from network.ue_manager import UEManager
from network.sector import Sector  # Import the Sector class
from logs.logger_config import ue_logger
from Config_files.config import Config
from database.database_manager import DatabaseManager

def reconcile_network_with_map(network_map, cell_manager):
    # Adjusted to use cell_manager for cell retrieval
    for gNodeB in network_map['gNodeBs']:
        for cell_config in gNodeB['cells']:
            cell_id = cell_config['cellId']
            cell = cell_manager.get_cell(cell_id)
            if cell:
                sector_ids = [sector['sectorId'] for sector in cell_config['sectors']]
                cell_sector_ids = [sector.sector_id for sector in cell.sectors]
                if set(sector_ids) != set(cell_sector_ids):
                    print(f"Mismatch in sectors for cell {cell_id}. Expected: {sector_ids}, Found: {cell_sector_ids}")
            else:
                print(f"Cell {cell_id} not found in initialized network.")

def initialize_network(base_dir, num_ues_to_launch=None):
    config = Config(base_dir)
    network_map = config.network_map_data
    db_manager = DatabaseManager.get_instance()

    # Use get_instance to ensure singleton pattern compliance
    gnodeb_manager = gNodeBManager.get_instance(base_dir)
    gNodeBs = gnodeb_manager.initialize_gNodeBs()

    assert gNodeBs is not None and len(gNodeBs) > 0, "gNodeBs initialization failed or returned empty."
    print(f"gNodeBs initialized: {gNodeBs}")

    # Initialize Cells using CellManager
    cell_manager = CellManager.get_instance(gNodeBs, db_manager)
    cells = cell_manager.initialize_cells(config.cells_config)

    assert cells is not None, "Cells initialization failed or returned None."
    #print(f"Cells initialized: {cells}")

    sector_manager = SectorManager.get_instance(db_manager) 
    sectors = sector_manager.initialize_sectors(config.sectors_config, gnodeb_manager, cell_manager)
    if num_ues_to_launch:
        ue_manager = UEManager.get_instance(base_dir=base_dir)
        ues = ue_manager.initialize_ues(num_ues_to_launch, cells, gNodeBs, config.ue_config)
        print("Initialized UEs:")
        for ue in ues:
            print(f"UE ID: {ue.ID}, Service Type: {ue.ServiceType}, Sector ID: {ue.ConnectedSector}, Cell ID: {ue.ConnectedCellID}, gNodeB ID: {ue.gNodeB_ID}")
            point = ue.serialize_for_influxdb()
            db_manager.insert_data(point)

    return gNodeBs, cells, sectors, ues, cell_manager