# init_ue.py
# Initialization of UEs
import random
import math
from database.database_manager import DatabaseManager
from .utils import random_location_within_radius
from Config_files.config_load import load_all_configs
from .ue import UE 
import logging
from network.network_state import NetworkState
from database.time_utils import get_current_time_ntp, server_pools

current_time = get_current_time_ntp()

# Create an instance of NetworkState
network_state = NetworkState()

def random_location_within_radius(latitude, longitude, radius_km):
    random_radius = random.uniform(0, radius_km)
    random_angle = random.uniform(0, 2 * math.pi)
    delta_lat = random_radius * math.cos(random_angle)
    delta_lon = random_radius * math.sin(random_angle)
    return (latitude + delta_lat, longitude + delta_lon)

def initialize_ues(num_ues_to_launch, gNodeBs, ue_config, network_state):
    ues = []
    db_manager = DatabaseManager(network_state)
    DEFAULT_BANDWIDTH_PARTS = [1, 2, 3, 4]  # Example default values
    ue_id_counter = len(network_state.ues) + 1
    
    # Calculate the total capacity of all cells
    total_capacity = sum(cell.MaxConnectedUEs for gNodeB in gNodeBs.values() for cell in gNodeB.Cells if cell.IsActive)

    # Check if the total number of UEs to be launched exceeds the total capacity
    if num_ues_to_launch > total_capacity:
        logging.error(f"Cannot launch {num_ues_to_launch} UEs, as it exceeds the total capacity of {total_capacity} UEs across all cells.")
        return []  # Return an empty list if the capacity is exceeded
    
    # Instantiate UEs from the configuration
    for _ in range(num_ues_to_launch):
        ue_data = random.choice(ue_config['ues']).copy()  # Make a copy to avoid mutating the original
        # Adjust the keys to match the UE constructor argument names
        if isinstance(ue_data['location'], dict):
            # Convert 'location' to a tuple only once
            ue_data['location'] = (ue_data['location']['latitude'], ue_data['location']['longitude'])
        else:
            logging.error("Location data is not in the expected format (dictionary with latitude and longitude).")
            continue
        ue_data['connected_cell_id'] = ue_data.pop('connectedCellId')
        ue_data['is_mobile'] = ue_data.pop('isMobile')
        ue_data['initial_signal_strength'] = ue_data.pop('initialSignalStrength')
        ue_data['rat'] = ue_data.pop('rat')
        ue_data['max_bandwidth'] = ue_data.pop('maxBandwidth')
        ue_data['duplex_mode'] = ue_data.pop('duplexMode')
        ue_data['tx_power'] = ue_data.pop('txPower')
        ue_data['modulation'] = ue_data.pop('modulation')
        ue_data['coding'] = ue_data.pop('coding')
        ue_data['mimo'] = str(ue_data.pop('mimo'))
        ue_data['processing'] = ue_data.pop('processing')
        ue_data['bandwidth_parts'] = ue_data.pop('bandwidthParts')
        ue_data['channel_model'] = ue_data.pop('channelModel')
        ue_data['velocity'] = ue_data.pop('velocity')
        ue_data['direction'] = ue_data.pop('direction')
        ue_data['traffic_model'] = ue_data.pop('trafficModel')
        ue_data['scheduling_requests'] = ue_data.pop('schedulingRequests')
        ue_data['rlc_mode'] = ue_data.pop('rlcMode')
        ue_data['snr_thresholds'] = ue_data.pop('snrThresholds')
        ue_data['ho_margin'] = ue_data.pop('hoMargin')
        ue_data['n310'] = ue_data.pop('n310')
        ue_data['n311'] = ue_data.pop('n311')
        ue_data['model'] = ue_data.pop('model')
        ue_data['service_type'] = ue_data.get('serviceType', None)
        ue_data.pop('IMEI', None)
        ue_data.pop('screensize', None)
        ue_data.pop('batterylevel', None)
        # Assign sequential UE ID
        ue_data['ue_id'] = f"UE{ue_id_counter}" 
        
        # Generate a unique UE ID
        ue_id = f"UE{ue_id_counter}"
        existing_ue_ids = [ue.ID for ue in network_state.ues]
        while ue_id in existing_ue_ids:
            ue_id_counter += 1
            ue_id = f"UE{ue_id_counter}"
        ue_data['ue_id'] = ue_id

        # Ensure modulation is a single scalar value, not a list
        if isinstance(ue_data['modulation'], list):
            ue_data['modulation'] = random.choice(ue_data['modulation'])
        
        # Check if 'bandwidthParts' exists in ue_data and handle it appropriately
        if 'bandwidthParts' not in ue_data:
            # If 'bandwidthParts' does not exist, provide a default value or handle the absence
            ue_data['bandwidth_parts'] = random.choice(DEFAULT_BANDWIDTH_PARTS)
        else:
            # If 'bandwidthParts' exists and it's a list, choose a random element
            if isinstance(ue_data['bandwidthParts'], list):
                ue_data['bandwidth_parts'] = random.choice(ue_data['bandwidthParts'])
            else:
                # If 'bandwidthParts' is not a list (i.e., it's a single value), use it as is
                ue_data['bandwidth_parts'] = ue_data['bandwidthParts']
        
        # Instantiate UE with the adjusted data
        ue = UE(**ue_data)
        # Assign UE to a random cell of a random gNodeB, if available
        selected_gNodeB = random.choice(list(gNodeBs.values()))
        if hasattr(selected_gNodeB, 'Cells'):  # Correct attribute name should be used here
            selected_cell = random.choice(selected_gNodeB.Cells)
            try:
                # Add the UE to the cell's ConnectedUEs list
                selected_cell.add_ue(ue, network_state)  # Pass the network_state object to the add_ue method
            # The network_state should be updated here if necessary
            
                ue.ConnectedCellID = selected_cell.ID
                logging.info(f"UE '{ue.ID}' has been attached to Cell '{ue.ConnectedCellID}' at '{current_time}'.")
            except Exception as e:
        # Handle the case where the cell is at maximum capacity
                logging.error(f"Failed to add UE '{ue.ID}' to Cell '{selected_cell.ID}' at '{current_time}': {e}")
        ###########################new change##########################################################################
        # Attempt to assign the UE to a cell
        assigned = False
        for gNodeB in gNodeBs.values():
            available_cells = [cell for cell in gNodeB.Cells if cell.current_ue_count < cell.MaxConnectedUEs and cell.IsActive]
            for cell in available_cells:
                try:
                    cell.add_ue(ue, network_state)
                    ue.ConnectedCellID = cell.ID
                    logging.info(f"UE '{ue.ID}' has been attached to Cell '{ue.ConnectedCellID}' at '{current_time}'.")
                    assigned = True
                    break  # Break out of the inner loop once the UE is successfully assigned
                except Exception as e:
                    logging.error(f"Failed to add UE '{ue.ID}' to Cell '{cell.ID}' at '{current_time}': {e}")
            if assigned:
                break  # Break out of the outer loop if the UE has been assigned
        
        if not assigned:
            logging.error(f"No available cell found for UE '{ue.ID}' at '{current_time}'.")
            continue  # Skip the rest of the loop and try with the next UE   
        ###################################################################################################################        
        # Serialize and write to InfluxDB
        point = ue.serialize_for_influxdb()
        db_manager.insert_data(point) 
        ues.append(ue)

        # Increment the UE ID counter for the next UE
        ue_id_counter += 1
    # Calculate the number of additional UEs needed
    additional_ues_needed = max(0, num_ues_to_launch - len(ues))

    # Create additional UEs if needed
    for _ in range(additional_ues_needed):
        selected_gNodeB = random.choice(list(gNodeBs.values()))
        available_cell = selected_gNodeB.find_underloaded_cell()
        random_location = random_location_within_radius(
            selected_gNodeB.Latitude, selected_gNodeB.Longitude, selected_gNodeB.CoverageRadius
        )
            
        if 'bandwidthParts' in ue_config['ues'][0]:
            bandwidth_parts = random.choice(ue_config['ues'][0]['bandwidthParts'])
        else:
            bandwidth_parts = random.choice(DEFAULT_BANDWIDTH_PARTS)
        
        new_ue = UE(
            ue_id=f"UE{ue_id_counter}",
            location=random_location,
            connected_cell_id=available_cell.ID if available_cell else None,
            is_mobile=True,
            initial_signal_strength=random.uniform(-120, -30),
            rat='NR',
            max_bandwidth=random.choice([5, 10, 15, 20]),
            duplex_mode='TDD',
            tx_power=random.randint(0, 23),
            modulation=random.choice(['QPSK', '16QAM', '64QAM']),
            coding=random.choice(['LDPC', 'Turbo']),
            mimo='2*2',
            processing=random.choice(['low', 'normal', 'high']),
            bandwidth_parts=bandwidth_parts,
            channel_model=random.choice(['urban', 'rural', 'suburban']),
            velocity=random.uniform(0, 50),
            direction=random.randint(0, 360),
            traffic_model=random.choice(['fullbuffer', 'bursty', 'periodic']),
            scheduling_requests=random.randint(1, 10),
            rlc_mode=random.choice(['AM', 'UM']),
            snr_thresholds=[random.randint(-20, 0) for _ in range(6)],
            ho_margin=random.randint(1, 10),
            n310=random.randint(1, 10),
            n311=random.randint(1, 10),
            model='generic',
            service_type=random.choice(['video', 'game', 'voice', 'data', 'IoT'])
        )
        ue_id_counter += 1  # Increment the counter outside of any conditions

        if available_cell:
            try:
                available_cell.add_ue(new_ue, network_state)
                new_ue.ConnectedCellID = available_cell.ID
                logging.info(f"UE '{new_ue.ID}' has been attached to Cell '{new_ue.ConnectedCellID}' at '{current_time}'.")
                ue_id_counter += 1  # Increment the ue_id_counter after successfully adding the UE
            except Exception as e:
                logging.error(f"Failed to add UE '{new_ue.ID}' to Cell '{available_cell.ID}': {e}")
            else:
                point = new_ue.serialize_for_influxdb()
                db_manager.insert_data(point)
                ues.append(new_ue)
        else:
            logging.error(f"No available cell found for UE '{new_ue.ID}' at '{current_time}'.")

    db_manager.close_connection()

    return ues

