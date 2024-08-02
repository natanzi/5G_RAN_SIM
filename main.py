import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
import logging
import time
import signal
import multiprocessing
from multiprocessing import Queue
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
from threading import Thread
from API_Gateway import API
from queue import Empty

def run_api(queue):
    def start_api_server():
        print("Starting API server on port 5000...")
        API.app.run(port=5000, use_reloader=False)

    api_server_thread = Thread(target=start_api_server)
    api_server_thread.daemon = True
    api_server_thread.start()

    while True:
        try:
            message = queue.get(timeout=1)
            if message == "SHUTDOWN":
                print("Shutting down API server...")
                break
        except Empty:
            continue

    # Implement proper shutdown for Flask (if needed)
    # For example, you might need to call a shutdown function on the API object

def generate_traffic_loop(traffic_controller, ue_list, network_load_manager, network_delay_calculator, db_manager, cell_manager):
    print(f"Debug: inside generate_traffic_loop of main.py ")  # Debugging line
    while True:
        for ue in ue_list:
            throughput_data = traffic_controller.calculate_throughput(ue)
            network_load_manager.network_measurement()
        time.sleep(1)

def main():
    logging.basicConfig(level=logging.INFO)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Set logging levels
    logging.getLogger('sector_load_logger').setLevel(logging.WARNING)
    logging.getLogger('cell_load_logger').setLevel(logging.WARNING)
    logging.getLogger('gnodbe_load_logger').setLevel(logging.WARNING)

    logo_text = create_logo()
    print(logo_text)

    # Start the API server in a separate process
    ipc_queue = Queue()
    api_proc = multiprocessing.Process(target=run_api, args=(ipc_queue,))
    api_proc.start()

    # Wait a moment to ensure API server starts
    time.sleep(1)

    # Database connection
    db_manager = DatabaseManager.get_instance()
    if db_manager.test_connection():
        print("Connection to InfluxDB successful.")
    else:
        print("Failed to connect to InfluxDB. Exiting...")
        return

    # Network Initialization
    gNodeB_manager = gNodeBManager.get_instance(base_dir=base_dir)
    print(f"Debug: Before initialize_network")
    print(f"Debug: gNodeB_manager: {gNodeB_manager}")
    print(f"Debug: base_dir: {base_dir}")
    gNodeBs, cells, sectors, ues, cell_manager = initialize_network(base_dir, num_ues_to_launch=5)
    

    # Add these print statements
    print(f"Debug: After initialize_network")
    print(f"Debug: gNodeBs: {gNodeBs}")
    print(f"Debug: cell_manager: {cell_manager}")
    print("Network Initialization Complete")

    # Additional setup
    sector_manager = SectorManager.get_instance(db_manager=db_manager)
    network_load_manager = NetworkLoadManager.get_instance(cell_manager, sector_manager, gNodeB_manager)
    

    ue_manager = UEManager.get_instance(base_dir)
    network_delay_calculator = NetworkDelay()

    traffic_controller_instance = TrafficController()
    traffic_thread = Thread(target=generate_traffic_loop, args=(traffic_controller_instance, ues, network_load_manager, network_delay_calculator, db_manager))
    traffic_thread.start()

    monitoring_thread = Thread(target=network_load_manager.monitoring)
    monitoring_thread.start()

    # Start CLI
    cli = SimulatorCLI(gNodeB_manager=gNodeB_manager, cell_manager=cell_manager, sector_manager=sector_manager, ue_manager=ue_manager, network_load_manager=network_load_manager, base_dir=base_dir)
    cli.cmdloop()

    # Signal handling for graceful shutdown
    def signal_handler(signum, frame):
        print("Signal received, shutting down gracefully...")
        ipc_queue.put("SHUTDOWN")
        api_proc.join(timeout=5)  # Wait for up to 5 seconds
        if api_proc.is_alive():
            print("API server didn't shut down gracefully. Terminating.")
            api_proc.terminate()
        print("API server shutdown complete.")
        traffic_thread.join()
        monitoring_thread.join()
        exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    main()