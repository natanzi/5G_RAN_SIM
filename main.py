import os
import logging
import time
from Config_files.config import Config
from logo import create_logo
from database.database_manager import DatabaseManager
from network.initialize_network import initialize_network
from traffic.traffic_generator import TrafficController
from network.ue_manager import UEManager
from network.gNodeB_manager import gNodeBManager
from network.cell_manager import CellManager
from network.sector_manager import SectorManager
from network.NetworkLoadManager import NetworkLoadManager
from logs.logger_config import gnodbe_load_logger, ue_logger
from network.network_delay import NetworkDelay
from simulator_cli import SimulatorCLI

def main():
    logging.basicConfig(level=logging.INFO)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_text = create_logo()
    print(logo_text)
    db_manager = DatabaseManager()
    time.sleep(1)

    # Use get_instance to ensure singleton pattern compliance
    gNodeB_manager = gNodeBManager.get_instance(base_dir=base_dir)
    gNodeBs, cells, sectors, ues, cell_manager = initialize_network(base_dir, num_ues_to_launch=10)
    print("Network Initialization Complete")
    print(f"Initialized sectors: {sectors}")

    # Note: No need to re-instantiate CellManager here as it's already done in initialize_network
    print(f"Cells in cell_manager after initialization: {cell_manager.cells}")

    # Note: SectorManager should also be instantiated using get_instance if it's not already done in initialize_network
    sector_manager = SectorManager.get_instance(db_manager=db_manager)

    network_load_manager = NetworkLoadManager(cell_manager, sector_manager)
    network_load_manager.log_and_write_loads()

    # UEManager should be accessed via get_instance, already done in initialize_network
    ue_manager = UEManager.get_instance(base_dir)

    network_delay_calculator = NetworkDelay()

    gNodeB_loads = network_load_manager.calculate_gNodeB_load()
    for gNodeB_id, load in gNodeB_loads.items():
        gnodbe_load_logger.info(f"gNodeB {gNodeB_id} Load: {load:.2f}%")

    for cell_id, cell in cell_manager.cells.items():
        cell_load = network_load_manager.calculate_cell_load(cell)
        serialized_data = cell.serialize_for_influxdb(cell_load)
        print(f"Serialized data for cell {cell_id}: {serialized_data.to_line_protocol()}")

    print(f"CellManager instance before CLI: {cell_manager}")

    # Start the CLI with the correctly instantiated managers
    cli = SimulatorCLI(gNodeB_manager=gNodeB_manager, cell_manager=cell_manager, sector_manager=sector_manager, ue_manager=ue_manager)
    cli.cmdloop()

if __name__ == "__main__":
    main()