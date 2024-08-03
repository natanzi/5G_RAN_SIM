##########################################################################################
# API.py is API Gateway of RANFusion and work with command_handler.py and also RANFUsion #
# Architecture to do some task.                                                          #
##########################################################################################
import os
import sys
import threading
import time
import signal
import traceback
import re
from dotenv import load_dotenv
from multiprocessing import Queue
from flask import Flask, request, jsonify, Response
from influxdb_client import InfluxDBClient

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import local modules
from logs.logger_config import API_logger
from network.ue_manager import UEManager
from network.command_handler import CommandHandler
from database.database_manager import DatabaseManager

# Load environment variables
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(base_dir, '.env')
load_dotenv(dotenv_path)

# Initialize Flask app
app = Flask(__name__)

# InfluxDB client setup
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG')
INFLUXDB_URL = os.getenv('INFLUXDB_URL')
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)

# Shutdown function
def shutdown_server():
    pid = os.getpid()
    os.kill(pid, signal.SIGTERM)

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    try:
        def shutdown_in_5():
            time.sleep(5)
            shutdown_server()

        threading.Thread(target=shutdown_in_5).start()
        return jsonify({"message": "Server will shut down in 5 seconds..."}), 202
    except Exception as e:
        return jsonify({"error": f"Failed to initiate shutdown: {str(e)}"}), 500

INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG')
INFLUXDB_URL = os.getenv('INFLUXDB_URL') 
client = InfluxDBClient(url=INFLUXDB_URL,token=INFLUXDB_TOKEN,org=INFLUXDB_ORG)

def check_for_shutdown_command(queue):
    """
    Periodically checks the queue for the shutdown command.
    If found, stops the Flask application.
    """
    while True:
        if not queue.empty():
            message = queue.get()
            if message == "SHUTDOWN":
                # Implement your shutdown logic here
                # For development server, you might set a global flag
                # For production with a server like Gunicorn, you would send a signal to shut down
                print("Shutdown command received. Implement shutdown logic here.")
                break
        time.sleep(1)  # Check every second

def run_api(queue):
    """
    Starts the API server and begins checking the queue for messages.
    """
    shutdown_thread = threading.Thread(target=check_for_shutdown_command, args=(queue,))
    shutdown_thread.start()
    
    # Start the Flask application
    app.run(debug=True, use_reloader=False)  # use_reloader=False is important to not spawn child processes
    
######################################################################################################################
# This is an API for deleting one UE from all places
@app.route('/api/del_ue', methods=['POST'])
def del_ue():
    data = request.json
    
    # Validate input data
    if 'ue_id' not in data:
        API_logger.error("Missing 'ue_id' in request data")
        return jsonify({'error': "Missing 'ue_id'"}), 400
    
    ue_id = data['ue_id']
    
    try:
        # Assuming CommandHandler.handle_command is properly implemented to handle 'del_ue' command
        # and now returns a boolean indicating success or failure
        result, message = CommandHandler.handle_command('del_ue', {'ue_id': ue_id})
        
        if result:
            API_logger.info(f"UE {ue_id} successfully removed.")
            return jsonify({'message': f'UE {ue_id} successfully removed', 'ue_id': ue_id}), 200
        else:
            API_logger.warning(f"Failed to remove UE {ue_id}: {message}")
            return jsonify({'error': f'Failed to remove UE {ue_id}', 'details': message}), 400
    except Exception as e:
        API_logger.error(f"An error occurred while removing UE {ue_id}: {e}")
        return jsonify({'error': 'An error occurred while removing UE', 'details': str(e)}), 500
    
########################################################################################################################
# This is an API for getting UE metrics like throughput, jitter, packet loss, and so on via API from InfluxDB in JSON format
@app.route('/api/ue_metrics', methods=['GET'])
def ue_metrics():
    ue_id = request.args.get('ue_id')

    # Validation for alphanumeric ue_id
    if not ue_id:
        return jsonify({'error': "Missing 'ue_id' parameter"}), 400
    elif not re.match("^[a-zA-Z0-9]+$", ue_id):
        return jsonify({'error': "Invalid 'ue_id' format. 'ue_id' must be alphanumeric."}), 400

    try:
        # Check if UE exists in the system
        from network.ue_manager import UEManager
        ue_manager = UEManager.get_instance()
        if not ue_manager.get_ue_by_id(ue_id):
            return jsonify({'error': f"UE {ue_id} not found in the system"}), 404

        db_manager = DatabaseManager.get_instance()
        metrics = db_manager.get_ue_metrics(ue_id)
        if metrics:
            response = jsonify({'metrics': metrics})
            response.headers['Content-Type'] = 'application/json'
            return response, 200
        else:
            return jsonify({'message': f'No metrics found for UE {ue_id}'}), 404
    except Exception as e:
        API_logger.error(f"An error occurred while retrieving metrics for UE {ue_id}: {e}")
        return jsonify({'error': 'An error occurred while retrieving metrics'}), 500

########################################################################################################################
# This is an API for adding a UE instance via API. We should send a JSON format of the UE info to add it.
@app.route('/api/add_ue', methods=['POST'])
def add_ue():
    data = request.json
    
    # Validate input data for required fields, for example, 'ue_id'
    if 'ue_id' not in data:
        API_logger.error("Missing 'ue_id' in request data")
        return jsonify({'error': "Missing 'ue_id'"}), 400
    
    try:
        # Pass the entire data dictionary to the CommandHandler
        result, message = CommandHandler.handle_command('add_ue', data)
        
        if result:
            API_logger.info(f"UE {data['ue_id']} added successfully.")
            return jsonify({'message': f"UE {data['ue_id']} added successfully"}), 200
        else:
            API_logger.warning(f"Failed to add UE {data['ue_id']}: {message}")
            return jsonify({'error': f"Failed to add UE {data['ue_id']}", 'details': message}), 400
    except Exception as e:
        API_logger.error(f"An error occurred while adding UE {data.get('ue_id', 'unknown')}: {e}")
        traceback.print_exc()
        return jsonify({'error': 'An error occurred while adding UE', 'details': str(e)}), 500

#########################################################################################################################
# This is an API for changing one or more attributes of the UE instance. For example, change one parameter in a live network.
@app.route('/api/update_ue', methods=['POST'])
def update_ue():
    data = request.json

    # Validate input data
    if 'ue_id' not in data:
        API_logger.error("Missing 'ue_id' in request data")
        return jsonify({'error': "Missing 'ue_id' in request data"}), 400

    # Extract UE ID and parameters to be updated
    ue_id = data['ue_id']
    update_params = {key: value for key, value in data.items() if key != 'ue_id'}

    try:
        # Use CommandHandler to update the UE
        update_result, message = CommandHandler._update_ue({'ue_id': ue_id, **update_params})

        if update_result:
            API_logger.info(f'UE {ue_id} updated successfully')
            return jsonify({'message': message}), 200
        else:
            API_logger.error(f'UE {ue_id} not found or update failed')
            return jsonify({'error': message}), 404

    except Exception as e:
        API_logger.error(f'An error occurred while updating UE: {str(e)}')
        return jsonify({'error': 'An error occurred while updating UE'}), 500

#########################################################################################################
# This is an API for starting the traffic of each UE
@app.route('/api/start_ue_traffic', methods=['POST'])
def start_ue_traffic():
    data = request.json
    if 'ue_id' not in data:
        API_logger.error("Missing 'ue_id' in request data")
        return jsonify({'error': "Missing 'ue_id'"}), 400

    result, message = CommandHandler.handle_command('start_ue_traffic', data)
    if result:
        return jsonify({'message': message}), 200
    else:
        API_logger.error(f"An error occurred while starting UE {data.get('ue_id', 'unknown')}")
        return jsonify({'error': message}), 400

#########################################################################################################
# This is an API for stopping the traffic of each UE
@app.route('/api/stop_ue_traffic', methods=['POST'])
def stop_ue_traffic():
    data = request.json
    if 'ue_id' not in data:
        API_logger.error("Missing 'ue_id' in request data")
        return jsonify({'error': "Missing 'ue_id'"}), 400
    
    API_logger.info(f"Received request to stop traffic for UE: {data['ue_id']}")  # Debug logging
    result, message = CommandHandler.handle_command('stop_ue_traffic', data)
    if result:
        return jsonify({'message': message}), 200
    else:
        API_logger.error(f"An error occurred while stopping UE {data.get('ue_id', 'unknown')}:")
        return jsonify({'error': message}), 400

#########################################################################################################
# This is an API for getting the load of each sector.
@app.route('/api/sector_load', methods=['GET'])
def sector_load():
    sector_id = request.args.get('sector_id')

    if not sector_id:
        return jsonify({'error': "Missing 'sector_id' parameter"}), 400
    # Additional validation can be added here

    try:
        db_manager = DatabaseManager.get_instance()
        load_metrics = db_manager.get_sector_load(sector_id)
        if load_metrics:
            return jsonify({'load_metrics': load_metrics}), 200
        else:
            return jsonify({'message': f'No load metrics found for sector {sector_id}'}), 404
    except Exception as e:
        API_logger.error(f"An error occurred while retrieving load metrics for sector {sector_id}: {e}")
        return jsonify({'error': 'An error occurred while retrieving load metrics'}), 500

######################################################################################################### 
# This is an API for changing the traffic pattern
@app.route('/api/set_traffic', methods=['POST'])
def set_traffic():
    data = request.json
    API_logger.info(f"Received request to set custom traffic: {data}")

    if not data:
        API_logger.error("No JSON data received in the request")
        return jsonify({'error': 'No data provided'}), 400

    required_fields = ['ue_id', 'traffic_factor']
    for field in required_fields:
        if field not in data:
            API_logger.error(f"Missing required field: {field}")
            return jsonify({'error': f"Missing required field: {field}"}), 400

    try:
        API_logger.info(f"Calling CommandHandler.handle_command with 'set_custom_traffic' and data: {data}")
        command_result, message = CommandHandler.handle_command('set_custom_traffic', data)
        API_logger.info(f"CommandHandler result: {command_result}, message: {message}")

        if command_result:  
            API_logger.info(f"Successfully set custom traffic for UE {data['ue_id']}")
            return jsonify({
                'success': True,
                'message': message,
                'ue_id': data['ue_id'],
                'traffic_factor': data['traffic_factor']
            }), 200
        else:
            API_logger.error(f"Failed to set custom traffic: {message}")
            return jsonify({'error': message}), 400
    except Exception as e:
        API_logger.error(f"An error occurred while setting custom traffic: {str(e)}")
        return jsonify({'error': 'An internal error occurred', 'details': str(e)}), 500

#########################################################################################################
# This is an API for deleting all information inside the database.
@app.route('/api/flush_database', methods=['POST'])
def flush_database():
    data = request.get_json()
    if not data or data.get('confirm') != 'yes':
        return jsonify({'error': 'Confirmation required'}), 400

    # Passing an empty dictionary as data for commands that do not require additional data.
    result, message = CommandHandler.handle_command('flush_all_data', {})

    if result:
        return jsonify({'message': message}), 200
    else:
        API_logger.error(f"Database flush failed: {message}")
        return jsonify({'error': message}), 500

#########################################################################################################
# This API returns the list of the current UEs in the database
@app.route('/api/ues', methods=['GET'])
def get_ues():
    try:
        # Initialize your DatabaseManager
        db_manager = DatabaseManager.get_instance()
        # Fetch UE IDs from the database
        ue_ids = db_manager.get_all_ue_ids()
        API_logger.info(f"UE IDs to be returned: {ue_ids}")  # Add this line
        # Return the list of UE IDs
        return jsonify({'ue_ids': ue_ids}), 200
    except Exception as e:
        # Log the error and return an error message
        # Make sure to set up logging appropriately
        API_logger.error(f"Failed to retrieve UE IDs: {e}")  
        return jsonify({'error': 'Failed to retrieve UE IDs'}), 500

#########################################################################################################
# This is an API for moving a UE from one sector to another place (sector)
# @app.route('/api/move_ue', methods=['POST'])
# def move_ue():
#     data = request.get_json()
#     ue_id = data.get('ue_id')

#     # Retrieve UE and validate existence
#     ue_manager = UEManager.get_instance()
#     ue = ue_manager.get_ue_by_id(ue_id)
#     if not ue:
#         return jsonify({'error': 'UE not found'}), 404
    
#     # Logic to move UE to new cell (simplified for example)
#     # This would involve more detailed logic to handle sector/gNodeB changes
#     success = ue_manager.move_ue_to_cell(ue_id,)
    
#     if success:
#         return jsonify({'message': 'UE moved successfully'}), 200
#     else:
#         return jsonify({'error': 'Failed to move UE'}), 500

###########################################################################################################
@app.route('/api/set_handover_algorithm', methods=['POST'])
def set_handover_algorithm():
    data = request.json
    algorithm_name = data.get('algorithm')
    if algorithm_name == 'rssi':
        LoadBalancer.get_instance().set_handover_algorithm(RSSIBasedHandover())
    elif algorithm_name == 'load_balancing':
        LoadBalancer.get_instance().set_handover_algorithm(LoadBalancingHandover())
    # Add more algorithms as needed
    return jsonify({'message': f'Handover algorithm set to {algorithm_name}'}), 200

###########################################################################################################
@app.route('/api/set_mobility_model', methods=['POST'])
def set_mobility_model():
    data = request.json
    model_name = data.get('model')
    if model_name == 'random_walk':
        LoadBalancer.get_instance().set_mobility_model(RandomWalkModel())
    elif model_name == 'linear':
        direction = data.get('direction', 0)
        LoadBalancer.get_instance().set_mobility_model(LinearModel(direction))
    # Add more models as needed
    return jsonify({'message': f'Mobility model set to {model_name}'}), 200

###########################################################################################################
@app.route('/api/get_ue_info', methods=['GET'])
def get_ue_info():
    ue_id = request.args.get('ue_id')
    if not ue_id:
        API_logger.error("Missing 'ue_id' in request parameters")
        return jsonify({'error': "Missing 'ue_id'"}), 400

    try:
        result, ue_info = CommandHandler.handle_command('get_ue_info', {'ue_id': ue_id})
        if result:
            return jsonify(ue_info), 200
        else:
            return jsonify({'error': ue_info}), 404
    except Exception as e:
        API_logger.error(f"An error occurred while retrieving UE info: {e}")
        return jsonify({'error': 'An error occurred while retrieving UE info'}), 500

###########################################################################################################
def shutdown_server():
    # Get the process ID
    pid = os.getpid()
    # Send the SIGTERM signal to the process
    os.kill(pid, signal.SIGTERM)

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    try:
        # Schedule the shutdown
        def shutdown_in_5():
            time.sleep(5)  # Wait for 5 seconds
            shutdown_server()

        threading.Thread(target=shutdown_in_5).start()
        
        return jsonify({"message": "Server will shut down in 5 seconds..."}), 202
    except Exception as e:
        return jsonify({"error": f"Failed to initiate shutdown: {str(e)}"}), 500
###########################################################################################################