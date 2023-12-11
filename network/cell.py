#Defines the Cell class, which is part of a gNodeB.// this is located inside network directory
import logging
from .network_state import NetworkState  # Import the NetworkState class
import datetime
from log.logger_config import ue_logger
from log.logger_config import cell_logger
import time 
class Cell:
    def __init__(self, cell_id, gnodeb_id, frequencyBand, duplexMode, tx_power, bandwidth, ssb_periodicity, ssb_offset, max_connect_ues, channel_model, trackingArea=None):
        self.ID = cell_id
        self.gNodeB_ID = gnodeb_id
        self.FrequencyBand = frequencyBand
        self.DuplexMode = duplexMode
        self.TxPower = tx_power
        self.Bandwidth = bandwidth
        self.SSBPeriodicity = ssb_periodicity
        self.SSBOffset = ssb_offset
        self.MaxConnectedUEs = max_connect_ues
        self.ChannelModel = channel_model
        self.TrackingArea = trackingArea 
        self.ConnectedUEs = []
        self.assigned_UEs = []  # Initialize the list of assigned UEs
        self.last_ue_update = None
        self.last_update = None
        # Logging statement should be here, after all attributes are set
        cell_logger.info(f"Cell '{cell_id}' has been created in gNodeB '{self.ID}' with max capacity {self.MaxConnectedUEs}.")
        
    @staticmethod
    def from_json(json_data):
        return Cell(
            cell_id=json_data["cell_id"],
            gnodeb_id=json_data["gnodeb_id"],
            frequencyBand=json_data["frequencyBand"],
            duplexMode=json_data["duplexMode"],
            tx_power=json_data["tx_power"],
            bandwidth=json_data["bandwidth"],
            ssb_periodicity=json_data["ssbPeriodicity"],
            ssb_offset=json_data["ssbOffset"],
            max_connect_ues=json_data["maxConnectUes"],
            channel_model=json_data["channelModel"],
            trackingArea=json_data.get("trackingArea")
        )
    def to_dict(self):
        return {
            'ID': self.ID,
            'gNodeB_ID': self.gNodeB_ID,
            'FrequencyBand': self.FrequencyBand,
            'DuplexMode': self.DuplexMode,
            'TxPower': self.TxPower,
            'Bandwidth': self.Bandwidth,
            'SSBPeriodicity': self.SSBPeriodicity,
            'SSBOffset': self.SSBOffset,
            'MaxConnectedUEs': self.MaxConnectedUEs,
            'ChannelModel': self.ChannelModel,
            'TrackingArea': self.TrackingArea,
            # Assuming you don't need to include the 'ConnectedUEs' list
        }
        # Method to get the count of active UEs and update the last attached cell and its gNodeB
    def update_ue_count(self):
            self.last_update = datetime.datetime.now()
            if self.ConnectedUEs:
                self.last_ue_update = {
                    'ue_id': self.ConnectedUEs[-1].ID,
                    'cell_id': self.ID,
                    'gnodeb_id': self.gNodeB_ID,
                    'timestamp': self.last_update
                }
            return len(self.ConnectedUEs)
        
    def add_ue(self, ue, network_state):
    # Check if the UE is already connected to any cell
        for cell_id, cell in network_state.cells.items():
            if ue in cell.ConnectedUEs:
                raise Exception(f"UE '{ue.ID}' is already connected to Cell '{cell_id}'.")

        if len(self.ConnectedUEs) < self.MaxConnectedUEs:
            self.ConnectedUEs.append(ue)
            print(f"UE '{ue.ID}' has been attached to Cell '{self.ID}'.")
            self.update_ue_count()
            # Update the network state here
            network_state.update_state(network_state.gNodeBs, list(network_state.cells.values()), list(network_state.ues.values()))
            ue_logger.info(f"UE with ID {ue.ID} added to Cell {self.ID} at {datetime.datetime.now()}")
            cell_logger.info(f"UE '{ue.ID}' has been added to Cell '{self.ID}'.")
        else:
            raise Exception("Maximum number of connected UEs reached for this cell.")

    def remove_ue(self, ue, network_state):
        if ue in self.ConnectedUEs:
            self.ConnectedUEs.remove(ue)
            print(f"UE '{ue.ID}' has been detached from Cell '{self.ID}'.")
            self.update_ue_count()
            # Update the network state here if necessary
            network_state.update_state(network_state.gNodeBs, list(network_state.cells.values()), list(network_state.ues.values()))
            ue_logger.info(f"UE with ID {ue.ID} removed from Cell {self.ID} at {datetime.datetime.now()}")
        else:
            print(f"UE '{ue.ID}' is not connected to Cell '{self.ID}' and cannot be removed.")
            ue_logger.warning(f"Attempted to remove UE with ID {ue.ID} from Cell {self.ID} which is not connected.")