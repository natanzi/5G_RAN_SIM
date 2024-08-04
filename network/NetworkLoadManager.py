#############################################################################################################################################
# NetworkLoadManager.py is located in network folder. The NetworkLoadManager class is responsible for managing the load across the          #
# network, including cells, sectors, and gNodeBs. It calculates the load based on various parameters such as the number of connected        #
# User Equipments (UEs), their throughput, and the capacity of network elements. Additionally, it performs load balancing to optimize       #
# network performance and logs network metrics for analysis. to address future needs around flexibly incorporating more advanced metrics    #
# like cell load, sector load, gnodb load, network load calulcattion, and load balancing techniques.                                        #
#############################################################################################################################################
from network.cell import Cell
from network.sector import Sector
from network.network_delay import NetworkDelay
from network.gNodeB_manager import gNodeBManager
from network.cell_manager import CellManager
from network.sector_manager import SectorManager
from database.database_manager import DatabaseManager
from network.loadbalancer import LoadBalancer
from logs.logger_config import cell_load_logger, sector_load_logger, gnodbe_load_logger, sector_logger
import time

class NetworkLoadManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(NetworkLoadManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls, cell_manager: CellManager, sector_manager: SectorManager, gNodeB_manager: gNodeBManager):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            # Initialize the instance only once
            cls._instance._initialize(cell_manager, sector_manager, gNodeB_manager)
        return cls._instance

    def _initialize(self, cell_manager: CellManager, sector_manager: SectorManager, gNodeB_manager: gNodeBManager):
        self.cell_manager = cell_manager
        self.sector_manager = sector_manager
        self.gNodeB_manager = gNodeB_manager
        self.db_manager = DatabaseManager.get_instance()
        self.load_balancer = LoadBalancer()
        
#####################################################################################################################   
    def calculate_sector_load(self, sector: Sector):
        """Calculate the load of a sector based on the number of connected UEs, their throughput, and its capacity.
        :param sector: An instance of the Sector class.
        :return: The load of the sector as a percentage.
        """
        if sector.capacity == 0:
            return 100  # Indicates the sector is overloaded if capacity is 0

        ue_count_load = (len(sector.connected_ues) / sector.capacity) * 100 if sector.capacity else 0

        # Encapsulate throughput capping logic
        total_capped_throughput = self.calculate_capped_throughput(sector)

        # Check for zero max throughput to default to 0 load
        throughput_load = (total_capped_throughput / sector.max_throughput) * 100 if sector.max_throughput else 0
    
        # Use constant weights for configurable relative importance
        COUNT_WEIGHT = 0.7
        TP_WEIGHT = 0.3
        sector_load = COUNT_WEIGHT * ue_count_load + TP_WEIGHT * throughput_load
        sector.sector_load_attribute = sector_load  # Update the sector's load attribute

        # Directly write the sector load to the database
        self.db_manager.write_sector_load(sector.sector_id, sector_load)

        return sector_load


    def calculate_capped_throughput(self, sector: Sector):
        """Calculate the total capped throughput for a sector.
        :param sector: An instance of the Sector class.
        :return: The total capped throughput.
        """
        max_share = sector.max_throughput * 0.1
        capped_ue_throughputs = [min(ue.throughput, max_share) for ue in sector.ues.values()]
        return sum(capped_ue_throughputs)
########################################################################################################################   
    def calculate_cell_load(self, cell: Cell):
        """
        Calculate the load of a cell based on the loads of its sectors.
        :param cell: An instance of the Cell class.
        :return: The load of the cell as a percentage.
        """
        # Check if the cell has sectors
        if not cell.sectors:
            return 0  # Return 0 if there are no sectors to avoid division by zero

        # Calculate the load for each sector and store the loads in a list
        sector_loads = [self.calculate_sector_load(sector) for sector in cell.sectors]

        # Calculate the average load of the cell based on its sectors
        cell_load = sum(sector_loads) / len(sector_loads)
        cell.cell_load = cell_load  # Update the cell's attribute

        # Directly write the cell load to the database using DatabaseManager's method
        self.db_manager.write_cell_load(cell.ID, cell_load)

        return cell_load
####################################################################################################################   
    def calculate_gNodeB_load(self):
        """
        Calculate the load of each gNodeB based on the loads of its cells and write it to the database.
        """
        gNodeB_loads = {}
        for gNodeB_id, gNodeB in self.cell_manager.gNodeBs.items():
            if not gNodeB.Cells:
                gNodeB_loads[gNodeB_id] = 0
                continue
        
            cell_loads = [self.calculate_cell_load(cell) for cell in gNodeB.Cells]
            gNodeB_load = sum(cell_loads) / len(cell_loads) if cell_loads else 0
            gNodeB_loads[gNodeB_id] = gNodeB_load
        
            # Update the gNodeB's load
            gNodeB.gnb_load = gNodeB_load
        
            # Serialize the gNodeB for InfluxDB
            point = gNodeB.serialize_for_influxdb()
        
            # Write the serialized data point to InfluxDB
            self.db_manager.insert_data(point)  
        
            # Log the load of each gNodeB
            gnodbe_load_logger.info(f"gNodeB {gNodeB_id} Load: {gNodeB_load:.2f}%")
        
        return gNodeB_loads
####################################################################################################################   
    def calculate_network_load(self):
        """
        Calculate the overall network load based on the loads of all cells.

        :return: The average load of the network as a percentage.
        """
        cells = self.cell_manager.cells.values()
        
        if not cells:
            return 0
        # Incorporate data volume into the calculation
        #total_data_volume = sum(ue.data_volume for ue in self.ue_manager.get_ues())
        cell_loads = [self.calculate_cell_load(cell) for cell in cells]
        network_load = sum(cell_loads) / len(cell_loads)

        return network_load
####################################################################################################################   
    def network_measurement(self):
        network_load = self.calculate_network_load()
        #print(f"Network Load: {network_load:.2f}%")
        network_load = self.calculate_network_load()
        # Calculate network delay
        network_delay_calculator = NetworkDelay()
        network_delay = network_delay_calculator.calculate_delay(network_load)
        #print(f"Network Delay: {network_delay} ms")

        # Get the total handover success count and failure count
        total_handover_success_count = sum(gnb.handover_success_count for gnb in self.gNodeB_manager.gNodeBs.values())
        total_handover_failure_count = sum(gnb.handover_failure_count for gnb in self.gNodeB_manager.gNodeBs.values())

        # Write network measurement (load, delay, handover counts) to the database
        self.db_manager.write_network_measurement(network_load, network_delay, total_handover_success_count, total_handover_failure_count)
        
##################################################################################################################     
    def monitoring(self, shutdown_event):
        import logging
        """
        Continuously monitors sector load, cell load, and network load.
        Triggers load balancing if any load exceeds the congestion threshold.
        """
        while not shutdown_event.is_set():
            try:
                # Calculate and log gNodeB loads
                gNodeB_loads = self.calculate_gNodeB_load()
                for gNodeB_id, load in gNodeB_loads.items():
                    gnodbe_load_logger.info(f"gNodeB {gNodeB_id} Load: {load:.2f}%")
                    if load > 80:  # Congestion threshold for gNodeBs
                        gnodbe_load_logger.warning(f"gNodeB {gNodeB_id} is congested with a load of {load:.2f}%.")
                        self.load_balancer.handle_load_balancing('gNodeB', gNodeB_id)

                # Calculate and log cell loads
                for cell_id, cell in self.cell_manager.cells.items():
                    cell_load = self.calculate_cell_load(cell)
                    cell_load_logger.info(f"Cell {cell_id} Load: {cell_load:.2f}%")
                    if cell_load > 80:  # Congestion threshold for cells
                        cell_load_logger.warning(f"Cell {cell_id} is congested with a load of {cell_load:.2f}%.")
                        self.load_balancer.handle_load_balancing('cell', cell_id)

                # Calculate and log sector loads
                for sector_id, sector in self.sector_manager.sectors.items():
                    sector_load = self.calculate_sector_load(sector)
                    sector_load_logger.info(f"Sector {sector_id} Load: {sector_load:.2f}%")
                    if sector_load > 80:  # Congestion threshold for sectors
                        sector_load_logger.warning(f"Sector {sector_id} is congested with a load of {sector_load:.2f}%.")
                        self.load_balancer.handle_load_balancing('sector', sector_id)

                # Calculate and log network load
                network_load = self.calculate_network_load()
                cell_load_logger.info(f"Network average load: {network_load:.2f}%")
                if network_load > 80:  # Congestion threshold for the network
                    cell_load_logger.warning(f"Network is congested with an average load of {network_load:.2f}%.")

                time.sleep(1)
            except Exception as e:
                logging.error(f"Error in monitoring loop: {str(e)}")
                # Optionally, you might want to break the loop or implement a retry mechanism

################################################Finding Neighbors#########################################################
    def get_sorted_entities_by_load(self, entity_id):
        if entity_id.startswith("sector"):  # Assuming sector IDs have a unique prefix
            return self.get_sorted_neighbor_sectors(entity_id)
        elif entity_id.startswith("cell"):  # Assuming cell IDs have a unique prefix
            return self.get_sorted_neighbor_cells(entity_id)
        elif entity_id.startswith("gNodeB"):  # Assuming gNodeB IDs have a unique prefix
            return self.get_sorted_neighbor_gNodeBs(entity_id)
        else:
            raise ValueError("Unknown entity type")

    def get_sorted_neighbor_sectors(self, sector_id):
        neighbors = self.sector_manager.get_neighbor_sectors(sector_id)
        # Calculate load for each neighbor
        neighbor_loads = [(neighbor_id, self.calculate_sector_load(neighbor)) for neighbor_id, neighbor in neighbors.items()]
        # Sort by load
        sorted_neighbors = sorted(neighbor_loads, key=lambda x: x[1], reverse=True)  # Assuming higher load should be first
        return [neighbor[0] for neighbor in sorted_neighbors]

    def get_sorted_neighbor_cells(self, cell_id):
        neighbors = self.cell_manager.get_neighbor_cells(cell_id)
        neighbor_loads = [(neighbor_id, self.calculate_cell_load(neighbor)) for neighbor_id, neighbor in neighbors.items()]
        sorted_neighbors = sorted(neighbor_loads, key=lambda x: x[1], reverse=True)  # Assuming higher load should be first
        return [neighbor[0] for neighbor in sorted_neighbors]

    def get_sorted_neighbor_gNodeBs(self, gNodeB_id):
        neighbors = self.gNodeBManager.get_neighbor_gNodeBs(gNodeB_id)
        neighbor_loads = [(neighbor_id, self.calculate_gNodeB_load().get(neighbor_id, 0)) for neighbor_id in neighbors]
        sorted_neighbors = sorted(neighbor_loads, key=lambda x: x[1], reverse=True)  # Assuming higher load should be first
        return [neighbor[0] for neighbor in sorted_neighbors]