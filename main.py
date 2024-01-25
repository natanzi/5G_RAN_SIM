import os
import logging
from Config_files.config import Config  # Import the new Config class
from logo import create_logo
from network.init_gNodeB import initialize_gNodeBs
from network.init_cell import initialize_cells
from network.init_sector import initialize_sectors
from network.init_ue import initialize_ues
from database.database_manager import DatabaseManager

def main():
    logo_text = create_logo()
    print(logo_text)
    
    logging.basicConfig(level=logging.INFO)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create an instance of Config here
    config = Config(base_dir)
    
    # Create an instance of DatabaseManager here
    db_manager = DatabaseManager()
    print(db_manager)
    
    # Initialize gNodeBs
    gNodeBs = initialize_gNodeBs(config.gNodeBs_config, db_manager)
    print("Initialized gNodeBs:")
    for gnb_id, gnb in gNodeBs.items():
        print(f"gNodeB ID: {gnb_id}, Details: {gnb}")
    
    # Initialize Cells
    cells = initialize_cells(gNodeBs, config.cells_config, db_manager)
    print("Initialized Cells:")
    for cell_id, cell in cells.items():
        print(f"Cell ID: {cell_id}, Details: {cell}")
    
    # Initialize Sectors
    sectors = initialize_sectors(config.sectors_config, cells, db_manager)
    print("Initialized Sectors:")
    for sector_id, sector in sectors.items():
        print(f"Sector ID: {sector_id}, Details: {sector}")
    
    # Initialize UEs
    num_ues_to_launch = 10  # This value should be set according to your needs
    ues = initialize_ues(num_ues_to_launch, sectors, config.ue_config, db_manager)
    print("Initialized UEs:")
    for ue in ues:
        print(f"UE ID: {ue.ID}, Sector ID: {ue.ConnectedSectorID}, Service Type: {ue.ServiceType}")

if __name__ == "__main__":
    main()