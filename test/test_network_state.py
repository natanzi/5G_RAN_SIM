#to insure that network state class is working
#test_network_state.py located in test folder
from network.network_state import NetworkState
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Assuming gNodeBs, cells, and ues have been initialized and populated elsewhere in your code

def find_ue_info(ue_id):
    # Instantiate the NetworkState class
    network_state = NetworkState()

    # Update the network state with the initialized components
    network_state.update_state(gNodeBs, cells, ues)

    # Retrieve the information for UE with ID 4
    ue_info = network_state.get_ue_info(ue_id)

    return ue_info

# Call the function with UE ID 4
ue_info = find_ue_info(4)

if ue_info:
    print(f"Information for UE 4: {ue_info}")
else:
    print("UE 4 information could not be found.")