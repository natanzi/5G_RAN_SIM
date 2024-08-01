######################################################################################################################################
# command_handler.py inside the network folder and owner of a command-based approach for adding, removing, or updating UEs or etc.   #
# Tthe CommandHandler class acts as middleware that can be utilized by both API.py and simulator_cli.py for executing     #
# commands such as add_ue. This design allows for a unified command processing mechanism across different interfaces of the system,  #
# ensuring consistency and reducing code duplication.                                                                                #
######################################################################################################################################
import os
from .ue import UE
from database.database_manager import DatabaseManager
from network.sector_manager import SectorManager
from logs.logger_config import API_logger
from flask import jsonify
from network.ue_manager import UEManager
from traffic.traffic_generator import TrafficController

class CommandHandler:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CommandHandler, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @staticmethod
    def handle_command(command_type, data):
        if command_type == 'add_ue':
            return CommandHandler._add_ue(data)
        elif command_type == 'del_ue':
            return CommandHandler._del_ue(data)
        elif command_type == 'update_ue':
            return CommandHandler._update_ue(data)
        elif command_type == 'start_ue_traffic':
            return CommandHandler._start_ue_traffic(data)
        elif command_type == 'stop_ue_traffic':
            return CommandHandler._stop_ue_traffic(data)
        elif command_type == 'set_custom_traffic':  
            return CommandHandler._set_custom_traffic(data)
        elif command_type == 'flush_all_data':
            return CommandHandler._flush_all_data(data)
        elif command_type == 'get_ue_info':
            return CommandHandler._get_ue_info(data)
        else:
            raise ValueError("Unsupported command type")

    @staticmethod
    def _del_ue(data):
        ue_id = data['ue_id']

        # Ensure UE ID is in the correct format
        if not ue_id.startswith("ue"):
            ue_id = "ue" + ue_id

        # Use UEManager to handle UE removal comprehensively
        ue_manager = UEManager.get_instance()
        
        # First, check if the UE exists in the system
        if ue_manager.get_ue_by_id(ue_id) is None:
            API_logger.error(f"UE {ue_id} not found in any sector or system")
            return jsonify({'error': f"UE {ue_id} not found in any sector or system"}), 404
        
        # Proceed with the removal process using UEManager's delete_ue method
        removed = ue_manager.delete_ue(ue_id)
        
        if removed:
            API_logger.info(f"UE {ue_id} removed successfully.")
            return jsonify({'message': f"UE {ue_id} removed successfully."}), 200
        else:
            API_logger.error(f"Failed to remove UE {ue_id}.")
            return jsonify({'error': f"Failed to remove UE {ue_id}."}), 500
        
    @staticmethod
    def _add_ue(data):
        ue_id = data.get("ue_id")
        ue_id_str = str(ue_id)  # Ensure it's a string if that's the expected format
        # Create the UE instance
        ue = UE(
            ue_id=data['ue_id_str'],
            imei=data['IMEI'],
            location=data['location'],
            connected_cell_id=data['connectedCellID'],
            gNodeB_id=data['gnodeb_id'],
            signal_strength=data['initialSignalStrength'],
            rat=data['rat'],
            max_bandwidth=data['maxBandwidth'],
            duplex_mode=data['duplexMode'],
            # Add other parameters as needed
            service_class=data.get('service_type'),  # Assuming service_class is equivalent to service_type
            tx_power=data['txPower'],
            modulation=data['modulation'],
            coding=data['coding'],
            mimo=data['mimo'],
            processing=data['processing'],
            bandwidth_parts=data['bandwidthParts'],
            channel_model=data['channelModel'],
            velocity=data['velocity'],
            direction=data['direction'],
            traffic_model=data['trafficModel'],
            scheduling_requests=data['schedulingRequests'],
            rlc_mode=data['rlcMode'],
            snr_thresholds=data['snrThresholds'],
            ho_margin=data['hoMargin'],
            n310=data['n310'],
            n311=data['n311'],
            model=data['model'],
            screensize=data['screensize'],
            batterylevel=data['batterylevel'],
            datasize=data['datasize']
        )

        # Assuming SectorManager and UEManager have methods to handle UE addition
        sector_manager = SectorManager.get_instance()
        ue_manager = UEManager.get_instance()

        # Add the UE to the sector
        success = sector_manager.add_ue_to_sector(data['sector_id'], ue)
        if success:
            # Optionally, start traffic generation for the newly added UE
            traffic_controller = TrafficController.get_instance()
            traffic_controller.start_ue_traffic(ue.ue_id)
            return jsonify({'message': 'UE successfully added'}), 200
        else:
            return jsonify({'error': 'Failed to add UE'}), 400
        
    @staticmethod
    def _start_ue_traffic(data):
        ue_id = data['ue_id']

        # Ensure UE ID is in the correct format
        if not ue_id.startswith("ue"):
            ue_id = "ue" + ue_id

        # Get an instance of the UEManager to check if the UE exists
        ue_manager = UEManager.get_instance()
        if not ue_manager.get_ue_by_id(ue_id):
            API_logger.error(f"UE {ue_id} not found.")
            return False, f"UE {ue_id} not found."

        # Proceed with starting the traffic since the UE exists
        traffic_controller = TrafficController.get_instance()
        started = traffic_controller.start_ue_traffic(ue_id)
        if started:
            API_logger.info(f"Traffic generation for UE {ue_id} has been started.")
            return True, f"Traffic generation for UE {ue_id} has been started."
        else:
            API_logger.error(f"Failed to start traffic for UE {ue_id}.")
            return False, f"Failed to start traffic for UE {ue_id}."

    @staticmethod
    def _stop_ue_traffic(data):
        ue_id = data['ue_id']

        # Ensure UE ID is in the correct format
        if not ue_id.startswith("ue"):
            ue_id = "ue" + ue_id

        # Get an instance of the UEManager to check if the UE exists
        ue_manager = UEManager.get_instance()
        ue = ue_manager.get_ue_by_id(ue_id)
        if not ue:
            API_logger.error(f"UE {ue_id} not found.")
            return False, f"UE {ue_id} not found."
        
        API_logger.debug(f"UE instance found: {ue}")  # Debug logging
        API_logger.debug(f"UE instance ID: {id(ue)}")  # Debug logging

        # Proceed with stopping the traffic since the UE exists
        traffic_controller = TrafficController.get_instance()
        stopped = traffic_controller.stop_ue_traffic(ue_id)
        if stopped:
            API_logger.info(f"Traffic generation for UE {ue_id} has been stopped.")
            return True, f"Traffic generation for UE {ue_id} has been stopped."
        else:
            API_logger.error(f"Failed to stop traffic for UE {ue_id}.")
            return False, f"Failed to stop traffic for UE {ue_id}."
    
    @staticmethod
    def _update_ue(data):
        ue_id = data['ue_id']
        update_params = {key: value for key, value in data.items() if key != 'ue_id'}

        try:
            # Retrieve the UE instance
            ue = UE.get_ue_instance_by_id(ue_id)

            if ue:
                # Update the UE parameters
                for key, value in update_params.items():
                    if hasattr(ue, key):
                        setattr(ue, key, value)
                        API_logger.info(f"Updated parameter '{key}' for UE {ue_id} to '{value}'")
                    else:
                        API_logger.warning(f"Parameter '{key}' not found for UE {ue_id}")

                API_logger.info(f"UE {ue_id} updated successfully")
                return True, f"UE {ue_id} updated successfully"
            else:
                API_logger.warning(f"UE {ue_id} not found")
                return False, f"UE {ue_id} not found"
        except Exception as e:
            API_logger.error(f"An error occurred while updating UE {ue_id}: {str(e)}")
#########################################################################################################
    @staticmethod
    def _set_custom_traffic(data):
        ue_id = data['ue_id']
        traffic_factor = data['traffic_factor']

        traffic_controller = TrafficController.get_instance()
        result = traffic_controller.set_custom_traffic(ue_id, traffic_factor)

        if result is not None:
            API_logger.info(f"Custom traffic set for UE {ue_id}. New traffic factor: {result}")
            return True, f"Custom traffic set for UE {ue_id}. New traffic factor: {result}"
        else:
            API_logger.error(f"Failed to set custom traffic for UE {ue_id}.")
            return False, f"Failed to set custom traffic for UE {ue_id}."
#########################################################################################################
    @staticmethod
    def _flush_all_data(data=None):  # Make data optional
        try:
            db_manager = DatabaseManager.get_instance()
            success = db_manager.flush_all_data()
            if success:
                API_logger.info("Database successfully flushed.")
                return True, "Database successfully flushed."
            else:
                API_logger.error("Failed to flush the database.")
                return False, "Failed to flush the database."
        except Exception as e:
            API_logger.error(f"An error occurred while flushing the database: {str(e)}")
            return False, f"An error occurred while flushing the database: {str(e)}"
#########################################################################################################
    @staticmethod
    def _get_ue_info(data):
        ue_id = data['ue_id'].strip().lower()  # Normalize the UE ID to lowercase
        API_logger.info(f"Attempting to retrieve info for UE with ID: {ue_id}")
        
        ue_manager = UEManager.get_instance()
        ue = ue_manager.get_ue_by_id(ue_id)
        
        if ue:
            API_logger.info(f"UE with ID {ue_id} found")
            return True, ue.__dict__  # Return all attributes of the UE instance
        else:
            API_logger.warning(f"UE with ID {ue_id} not found")
            return False, {'error': f'UE with ID {ue_id} not found'}
#########################################################################################################
    @staticmethod
    def _get_ue_info(data):
        ue_id = data['ue_id'].strip().lower()  # Normalize the UE ID to lowercase
        API_logger.info(f"Attempting to retrieve info for UE with ID: {ue_id}")
        
        ue_manager = UEManager.get_instance()
        ue = ue_manager.get_ue_by_id(ue_id)
        
        if ue:
            API_logger.info(f"UE with ID {ue_id} found")
            return True, ue.__dict__  # Return all attributes of the UE instance
        else:
            API_logger.warning(f"UE with ID {ue_id} not found")
            return False, {'error': f'UE with ID {ue_id} not found'}