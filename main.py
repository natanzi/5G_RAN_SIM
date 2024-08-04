import os
from dotenv import load_dotenv
import logging
import time
import signal
import multiprocessing
from multiprocessing import Queue
from threading import Thread
from queue import Empty
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
from API_Gateway import API
#Add this global variable at the top of the file
import threading
from threading import Event
shutdown_event = threading.Event()  

def run_api(queue, shutdown_event):
    def start_api_server():
        print("Starting API server on port 5000...")
        API.app.run(port=5000, use_reloader=False)

    api_server_thread = Thread(target=start_api_server)
    api_server_thread.daemon = True
    api_server_thread.start()

    while not shutdown_event.is_set():
        try:
            message = queue.get(timeout=1)
            if message == "SHUTDOWN":
                print("Shutting down API server...")
                break
        except Empty:
            continue

def generate_traffic_loop(traffic_controller, ue_list, network_load_manager, network_delay_calculator, db_manager, cell_manager, shutdown_event):
    logging.debug("Starting traffic generation loop")
    while not shutdown_event.is_set():
        for ue in ue_list:
            throughput_data = traffic_controller.calculate_throughput(ue)
            network_load_manager.network_measurement()
        time.sleep(1)

def initialize_components(base_dir):
    config = Config(base_dir)
    db_manager = DatabaseManager.get_instance()
    if not db_manager.test_connection():
        raise ConnectionError("Failed to connect to InfluxDB")

    gNodeB_manager = gNodeBManager.get_instance(base_dir=base_dir)
    gNodeBs, cells, sectors, ues, cell_manager = initialize_network(base_dir, num_ues_to_launch=config.ue_config.get('num_ues_to_launch', 5))
    
    sector_manager = SectorManager.get_instance(db_manager=db_manager)
    network_load_manager = NetworkLoadManager.get_instance(cell_manager, sector_manager, gNodeB_manager)
    ue_manager = UEManager.get_instance(base_dir)
    network_delay_calculator = NetworkDelay()

    return config, db_manager, gNodeB_manager, cell_manager, sector_manager, network_load_manager, ue_manager, network_delay_calculator, gNodeBs, cells, sectors, ues

def main():
    logging.basicConfig(level=logging.INFO)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(base_dir, '.env')
    load_dotenv(dotenv_path)

    logging.getLogger('sector_load_logger').setLevel(logging.WARNING)
    logging.getLogger('cell_load_logger').setLevel(logging.WARNING)
    logging.getLogger('gnodbe_load_logger').setLevel(logging.WARNING)

    print(create_logo())

    ipc_queue = Queue()
    api_proc = multiprocessing.Process(target=run_api, args=(ipc_queue,))
    api_proc.start()

    time.sleep(1)  # Wait for API server to start

    try:
        config, db_manager, gNodeB_manager, cell_manager, sector_manager, network_load_manager, ue_manager, network_delay_calculator, gNodeBs, cells, sectors, ues = initialize_components(base_dir)
    except Exception as e:
        logging.error(f"Failed to initialize components: {e}")
        return
    
    shutdown_event = Event()
    traffic_controller_instance = TrafficController()
    traffic_thread = Thread(target=generate_traffic_loop, args=(traffic_controller_instance, ues, network_load_manager, network_delay_calculator, db_manager, cell_manager, shutdown_event))   
    monitoring_thread = Thread(target=network_load_manager.monitoring)
    monitoring_thread.start()

    cli = SimulatorCLI(gNodeB_manager=gNodeB_manager, cell_manager=cell_manager, sector_manager=sector_manager, ue_manager=ue_manager, network_load_manager=network_load_manager, base_dir=base_dir, shutdown_event=shutdown_event)
    def signal_handler(signum, frame):
        print("Signal received, shutting down gracefully...")
        logging.info("Signal received, shutting down gracefully...")
        shutdown_event.set()
        ipc_queue.put("SHUTDOWN")
        api_proc.join(timeout=5)
        if api_proc.is_alive():
            logging.warning("API server didn't shut down gracefully. Terminating.")
            api_proc.terminate()
        logging.info("API server shutdown complete.")
        traffic_thread.join()
        monitoring_thread.join()
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    cli = SimulatorCLI(
        gNodeB_manager=gNodeB_manager,
        cell_manager=cell_manager,
        sector_manager=sector_manager,
        ue_manager=ue_manager,
        network_load_manager=network_load_manager,
        base_dir=base_dir,
        shutdown_event=shutdown_event
    )

if __name__ == "__main__":
    main()