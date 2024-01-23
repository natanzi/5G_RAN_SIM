#Defines the gNodeB class with properties like ID, location, cells, etc. thi is located insde network directory
import os
import json
import random
import time
from database.time_utils import get_current_time_ntp
import logging
from utils.location_utils import get_nearest_gNodeB, get_ue_location_info
from network.cell import Cell
from network.init_cell import initialize_cells
from .init_cell import load_json_config
from network.network_state import NetworkState
from time import sleep
from logs.logger_config import cell_logger, gnodeb_logger
from datetime import datetime
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS, WritePrecision
from database.time_utils import get_current_time_ntp, server_pools
from multiprocessing import Lock

current_time = get_current_time_ntp()

def load_gNodeB_config():
    # Correct the path to point to the 'Config_files' directory
    # This assumes that 'Config_files' is a direct subdirectory of the base directory where 'main.py' is located
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, 'Config_files', 'gNodeB_config.json')

    with open(file_path, 'r') as file:
        return json.load(file)

##Using the function to load the configuration
gNodeBs_config = load_gNodeB_config()

class gNodeB:
    def __init__(self, gnodeb_id, latitude, longitude, coverageRadius, power, frequency, bandwidth, location, region, maxUEs, cellCount, handoverMargin, handoverHysteresis, timeToTrigger, interFreqHandover, xnInterface, sonCapabilities, loadBalancingOffset, cellIds, MeasurementBandwidth=None, BlacklistedCells=None, **kwargs):
        print("Debug Start: __init__ method in gNodeB class.")
        self.ID = gnodeb_id
        self.Latitude = latitude
        self.Longitude = longitude
        self.CoverageRadius = coverageRadius
        self.TransmissionPower = power
        self.Frequency = frequency
        self.Bandwidth = bandwidth
        self.Location = location
        self.Region = region
        self.MaxUEs = maxUEs
        self.CellCount = cellCount
        self.Cells = []  # This will hold Cell instances associated with this gNodeB
        self.HandoverMargin = handoverMargin
        self.HandoverHysteresis = handoverHysteresis
        self.TimeToTrigger = timeToTrigger
        self.InterFreqHandover = interFreqHandover
        self.XnInterface = xnInterface
        self.SONCapabilities = sonCapabilities
        self.MeasurementBandwidth = MeasurementBandwidth
        self.BlacklistedCells = BlacklistedCells
        self.LoadBalancingOffset = loadBalancingOffset
        self.CellIds = cellIds
        self.handover_success_count = 0
        self.handover_failure_count = 0
        self.lock = Lock()
        gnodeb_logger.info(f"gNodeB '{self.ID}' has been launched with {self.CellCount} cells at '{current_time}'.")
        print(f"Debug End: gNodeB '{self.ID}' initialized with {self.CellCount} cells.")

        # Handle any additional keyword arguments
        for key, value in kwargs.items():
            setattr(self, key, value)
        print(f"gNodeB '{self.ID}' has been launched with {self.CellCount} cells.")
        time.sleep(1)  # Delay for 1 second

    @staticmethod
    def from_json(json_data):
        gNodeBs = []
        for item in json_data["gNodeBs"]:
            gnodeb = gNodeB(**item)  # Unpack the dictionary directly
            gNodeBs.append(gnodeb)
        return gNodeBs
    ###############################################################################################################
    # add serialization methods to the gNodeB class to convert gNodeB instances into a format suitable for InfluxDB
    def serialize_for_influxdb(self):
        point = Point("gnodeb_metrics") \
            .tag("gnodeb_id", self.ID) \
            .tag("entity_type", "gnodeb") 

        # Convert the location list to a string if it's not None
        location_str = ','.join(map(str, self.Location)) if self.Location is not None else None

        # Ensure the 'region' field is a string
        region_str = str(self.Region) if self.Region is not None else None

        fields = {
            "latitude": self.Latitude,
            "longitude": self.Longitude,
            "coverage_radius": self.CoverageRadius,
            "transmission_power": self.TransmissionPower,
            "frequency": self.Frequency,
            "region": region_str,  # Use the converted string for 'region'
            "max_ues": self.MaxUEs,
            "cell_count": self.CellCount,
            "measurement_bandwidth": self.MeasurementBandwidth,
            "blacklisted_cells": self.BlacklistedCells,
            "handover_success_count": self.handover_success_count,
            "handover_failure_count": self.handover_failure_count,
            "location": location_str,  
            "bandwidth": self.Bandwidth,
            "handover_margin": self.HandoverMargin,
            "handover_hysteresis": self.HandoverHysteresis,
            "time_to_trigger": self.TimeToTrigger,
            "inter_freq_handover": self.InterFreqHandover,
            "xn_interface": self.XnInterface,
            "son_capabilities": self.SONCapabilities,
            "load_balancing_offset": self.LoadBalancingOffset,
            "cell_ids": ','.join(map(str, self.CellIds)) if self.CellIds is not None else None
        }

        for field, value in fields.items():
            if value is not None:
                point = point.field(field, value)

        point = point.time(time.time_ns(), WritePrecision.NS)
        return point
######################################################################################################
##################################################Cell and UE Management##########################
    def get_ue_by_id(self, ue_id):
        # Retrieve the UE object from the internal list of UEs managed by this gNodeB
        # Assuming self.ues is a dictionary with UE IDs as keys and UE objects as values
        return self.ues.get(ue_id, None)
################################################################################################
    def delete_cell(self, cell_id):
        # Start of method execution
        print(f"Debug Start: delete_cell method in gNodeB class for cell_id {cell_id}.")

        # Find the cell to be deleted
        cell_to_delete = next((cell for cell in self.Cells if cell.ID == cell_id), None)
        if cell_to_delete is None:
            print(f"No cell with ID {cell_id} found in gNodeB with ID {self.ID}.")
            print(f"Debug End: delete_cell method in gNodeB class for cell_id {cell_id}.")
            return

        # Attempt to handover UEs to other cells
        from .handover_utils import perform_handover, check_handover_feasibility
        for ue_id in cell_to_delete.ConnectedUEs:
            ue = self.find_ue_by_id(ue_id)
            if ue:
                # Determine a new cell for handover
                new_cell = self.find_available_cell()  # This method should identify a suitable cell
                if new_cell and check_handover_feasibility(self.network_state, new_cell.ID, ue):
                    # Perform handover to the new cell
                    print(f"Handover started in GNB function {self.ID} to cell {new_cell.ID} for UE with ID {ue.ID}.")
                    perform_handover(self, ue, new_cell, self.network_state)
                else:
                    print(f"No available or suitable cell for UE with ID {ue.ID} to handover.")

        # Remove the cell from the Cells list
        self.Cells.remove(cell_to_delete)
        print(f"Debug: Cell with ID {cell_id} has been deleted from gNodeB with ID {self.ID}. Remaining cells: {[c.ID for c in self.Cells]}")
        cell_logger.info(f"Cell with ID {cell_id} has been deleted from gNodeB with ID {self.ID}. Remaining cells: {[c.ID for c in self.Cells]}")

        # End of method execution
        print(f"Debug End: delete_cell method in gNodeB class for cell_id {cell_id}.")
###################################################################################################
    def all_ues(self):
        """
        Returns a list of all UE objects managed by this gNodeB.
        """
        print("Debug Start: all_ues method in gNodeB class.")
        all_ue_objects = []
        for cell in self.Cells:
            # Assuming each cell has a list of UE IDs in a property called ConnectedUEs
            for ue_id in cell.ConnectedUEs:
                # Assuming there is a method to find a UE by its ID
                ue = self.find_ue_by_id(ue_id)
                if ue:
                    all_ue_objects.append(ue)
        print("Debug End: all_ues method in gNodeB class.")
        return all_ue_objects
###################################################################################################
    def find_cell_by_id(self, cell_id):
        """
        Finds a cell by its ID within the gNodeB's list of cells.
        :param cell_id: The ID of the cell to find.
        :return: The cell with the matching ID or None if not found.
        """
        print(f"Debug Start: find_cell_by_id method in gNodeB class for cell_id {cell_id}.")
        for cell in self.Cells:
            if cell.ID == cell_id:
                print(f"Debug End: find_cell_by_id method in gNodeB class for cell_id {cell_id}.")
                return cell
        print(f"Debug End: find_cell_by_id method in gNodeB class for cell_id {cell_id}.")
        return None
###################################################################################################
    def has_cell(self, cell_id):
        print(f"Debug Start: has_cell method in gNodeB class for cell_id {cell_id}.")
        result = any(cell.ID == cell_id for cell in self.Cells)
        print(f"Debug End: has_cell method in gNodeB class for cell_id {cell_id}.")
        return result
###################################################################################################
    def update_cell_capacity(self, new_capacity):
        """
        Updates the cell capacity of the gNodeB.
        :param new_capacity: The new capacity to set.
        """
        print(f"Debug Start: update_cell_capacity method in gNodeB class with new_capacity {new_capacity}.")
        # Check if the new capacity is valid
        if new_capacity < 0:
            raise ValueError("Cell capacity cannot be negative.")

        # Update the CellCount attribute
        self.CellCount = new_capacity

        # Log the change
        print(f"Debug: gNodeB '{self.ID}' cell capacity updated to {self.CellCount}.")
        cell_logger.info(f"gNodeB '{self.ID}' cell capacity updated to {self.CellCount}.")
        print(f"Debug End: update_cell_capacity method in gNodeB class with new_capacity {new_capacity}.")

###################################################################################################
    def add_cell_to_gNodeB(self, cell, network_state):
        with self.lock:  # Ensure thread safety
            try:
                print(f"Debug: Attempting to add cell {cell.ID} to gNodeB {self.ID}")
                current_cell_ids = [c.ID for c in self.Cells]
                print(f"Debug: Current cells in gNodeB {self.ID} before adding: {current_cell_ids}")
                cell_logger.info(f"Current cells in gNodeB {self.ID} before adding: {current_cell_ids}")

                # Proactive check to prevent adding a cell with a duplicate ID
                if cell.ID in current_cell_ids:
                    print(f"Debug: Cell {cell.ID} is already added to gNodeB {self.ID}. Ignoring.")
                    cell_logger.warning(f"Cell {cell.ID} is already added to gNodeB {self.ID}. Ignoring.")
                    return

                if len(self.Cells) >= self.CellCount:
                    print(f"Debug: gNodeB {self.ID} has reached its maximum cell capacity. Cannot add more cells.")
                    cell_logger.error(f"gNodeB {self.ID} has reached its maximum cell capacity. Cannot add more cells.")
                    return

                # Set the parent gNodeB reference for the cell
                cell.set_gNodeB(self)

                # Add the cell to the gNodeB's list of cells
                self.Cells.append(cell)
                print(f"Debug: Cell {cell.ID} has been added to gNodeB {self.ID}.")
                cell_logger.info(f"Cell '{cell.ID}' has been added to gNodeB '{self.ID}'.")

                # Update the NetworkState to include the new cell
                network_state.add_cell(cell)

                # Add sectors to the cell if they are not already present
                for sector in cell.sectors:
                    if not cell.has_sector(sector):
                        self.add_sector_to_cell(sector, cell)
                        print(f"Debug: Sector {sector.ID} has been added to Cell {cell.ID}.")
                        cell_logger.info(f"Sector '{sector.ID}' has been added to Cell '{cell.ID}'.")

                # Reactive check to ensure no duplicate cells have been added
                self.verify_no_duplicate_cells()

                # Delay for 1 second as per the original requirement
                time.sleep(1)
            except Exception as e:
                print(f"Error: An exception occurred while adding cell {cell.ID} to gNodeB {self.ID}: {e}")
                cell_logger.error(f"An exception occurred while adding cell {cell.ID} to gNodeB {self.ID}: {e}")

    def verify_no_duplicate_cells(self):
        with self.lock:
            cell_ids = [cell.ID for cell in self.Cells]
            if len(cell_ids) != len(set(cell_ids)):
                raise ValueError("Duplicate Cell IDs detected after addition.")
###################################################################################################
    def add_sector_to_cell(self, sector, cell, network_state):
    # Check if the cell exists in this gNodeB
        if cell not in self.Cells:
            raise ValueError(f"Cell '{cell.ID}' does not exist in gNodeB '{self.ID}'")
    
    # Check if the sector already exists in the cell
        if cell.has_sector(sector):
            raise ValueError(f"Sector '{sector.ID}' already exists in Cell '{cell.ID}'")
    
    # Add the sector to the cell's list of sectors
        cell.add_sector(sector)
    
    # Update the NetworkState to include the new sector
        network_state.add_sector(sector)
    
    # Log the addition of the sector
        cell_logger.info(f"Sector '{sector.ID}' has been added to Cell '{cell.ID}' in gNodeB '{self.ID}'.")
###################################################################################################
#####################################Load Calculation##############################################
    def calculate_cell_load(self, cell, traffic_controller):
        print(f"Debug Start: calculate_cell_load method in gNodeB class for cell ID {cell.ID}.")
        # Calculate the load based on the number of connected UEs
        ue_based_load = len(cell.ConnectedUEs) / cell.MaxConnectedUEs if cell.MaxConnectedUEs > 0 else 0

        # Calculate the load based on the throughput
        total_throughput = 0
        for ue in cell.assigned_UEs:
            # Assume a function to calculate UE throughput exists
            ue_throughput = self.calculate_ue_throughput(ue)
            total_throughput += ue_throughput
        max_throughput_bytes = 100 * 1024 * 1024
        throughput_based_load = total_throughput / max_throughput_bytes if max_throughput_bytes > 0 else 0

        # Retrieve quality metrics (jitter, packet loss, delay) for each UE from the TrafficController
        jitter_total = sum(traffic_controller.get_traffic_parameters(ue)['jitter'] for ue in cell.assigned_UEs)
        packet_loss_total = sum(traffic_controller.get_traffic_parameters(ue)['packet_loss'] for ue in cell.assigned_UEs)
        delay_total = sum(traffic_controller.get_traffic_parameters(ue)['delay'] for ue in cell.assigned_UEs)

        # Calculate average quality metrics across all UEs
        num_ues = len(cell.assigned_UEs)
        jitter_avg = jitter_total / num_ues if num_ues > 0 else 0
        packet_loss_avg = packet_loss_total / num_ues if num_ues > 0 else 0
        delay_avg = delay_total / num_ues if num_ues > 0 else 0

        # Combine all loads with appropriate weights
        combined_load = (0.4 * ue_based_load) + (0.4 * throughput_based_load) + (0.2 * (jitter_avg + packet_loss_avg + delay_avg) / 3)

        # Convert combined load to a percentage
        combined_load_percentage = combined_load * 100
        print(f"Debug End: calculate_cell_load method in gNodeB class for cell ID {cell.ID}. Load calculated: {combined_load_percentage}%")
        return combined_load_percentage

##########################################################################################################################
    def find_underloaded_cell(self):
        print("Debug Start: find_underloaded_cell method in gNodeB class.")
        underloaded_cell = None
        lowest_load = float('inf')
        for cell in self.Cells:
            cell_load = self.calculate_cell_load(cell, traffic_controller)
            if cell_load < 0.8 and cell_load < lowest_load:  # Threshold is 80%
                underloaded_cell = cell
                lowest_load = cell_load
        print(f"Debug End: find_underloaded_cell method in gNodeB class. Underloaded cell found: {underloaded_cell.ID if underloaded_cell else 'None'} with load: {lowest_load}")
        cell_logger.info(f"Underloaded cell found: {underloaded_cell.ID if underloaded_cell else 'None'} with load: {lowest_load}")
        return underloaded_cell
##########################################################################################################################
    def select_ues_for_load_balancing(self, overloaded_cell, underloaded_cell):
        print("Debug Start: select_ues_for_load_balancing method in gNodeB class.")
        ue_objects = [self.get_ue_by_id(ue_id) for ue_id in overloaded_cell.ConnectedUEs]
        # Prioritize UEs based on service type and data usage
        prioritized_ues = sorted(ue_objects, key=lambda ue: (ue.serviceType in ['video', 'game', 'data'], ue.get_data_usage()), reverse=True)
        # Select a subset of UEs for handover
        ues_to_move = prioritized_ues[:len(prioritized_ues) // 3]
        print("Debug End: select_ues_for_load_balancing method in gNodeB class.")
        return ues_to_move
############################################################################################################################
    def find_available_cell(self):
        print("Debug Start: find_available_cell method in gNodeB class.")
        best_cell = None
        lowest_load = float('inf')
        for cell in self.Cells:
            cell_load = self.calculate_cell_load(cell)
            if cell_load < 0.8 and cell_load < lowest_load:  # 0.8 represents 80% load
                best_cell = cell
                lowest_load = cell_load
        print(f"Debug End: find_available_cell method in gNodeB class. Available cell found: {best_cell.ID if best_cell else 'None'} with load: {lowest_load}")
        return best_cell
#########################################################################################################
#######################################Periodic Updates###############################################
    def update(self):
        from network.handover_utils import handle_load_balancing, monitor_and_log_cell_load
        # Log before handling load balancing
        print(f"Debug: Starting load balancing for gNodeB {self.ID}")
        gnodeb_logger.info(f"Starting load balancing for gNodeB {self.ID}")
        # Call this method regularly to update handover decisions
        handle_load_balancing(self, self.calculate_cell_load, self.find_underloaded_cell, self.select_ues_for_load_balancing)
        # Log after handling load balancing
        print(f"Debug: Completed load balancing for gNodeB {self.ID}")
        gnodeb_logger.info(f"Completed load balancing for gNodeB {self.ID}")
        # Now also call monitor_and_log_cell_load to log the cell load
        monitor_and_log_cell_load(self)
        # Log after monitoring and logging cell load
        print(f"Debug: Completed monitoring and logging cell load for gNodeB {self.ID}")
        gnodeb_logger.info(f"Completed monitoring and logging cell load for gNodeB {self.ID}")
######################################################################################################
