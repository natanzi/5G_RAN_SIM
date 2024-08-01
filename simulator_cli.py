#################################################################################################################################
# simulator_cli.py is located in root directory to allows you to type commands like ue-list to see the list of current UEs.     #
# execute various commands to manage and monitor the network's state, including listing gNodeBs, cells, sectors, UEs, and       #
# their respective logs and KPIs. It also supports commands for starting and stopping UE traffic, adding or deleting UEs, and   #
# manually triggering load balancing.                                                                                           #
#################################################################################################################################
import cmd
from colorama import init, Fore, Style as ColoramaStyle
init(autoreset=True)
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
import time
from prettytable import PrettyTable
from threading import Event
import os
import threading
from network.ue import UE
from blessed import Terminal
from database.database_manager import DatabaseManager
# Assuming these are your custom modules for managing various aspects of the network simulator
from network.ue_manager import UEManager
from network.gNodeB_manager import gNodeBManager
from network.cell_manager import CellManager
from network.sector_manager import SectorManager
from network.NetworkLoadManager import NetworkLoadManager
from traffic.traffic_generator import TrafficController
from network.ue import UE
from network.sector import global_ue_ids

cli_style = Style.from_dict({
    'prompt': 'fg:green bold',  # Use 'green' instead of 'ansi.green'
})


# Define your aliases and commands in a more flexible structure
# For the purpose of this example, it's defined within the code, but it could be external
alias_config = {
    'aliases': [
        {'alias': 'gnb', 'command': 'gnb_list'},
        {'alias': 'cell', 'command': 'cell_list'},
        {'alias': 'sector', 'command': 'sector_list'},
        {'alias': 'ue', 'command': 'ue_list'},
        {'alias': 'ulog', 'command': 'ue_log'},
        {'alias': 'ukpi', 'command': 'ue_kpis'},
        {'alias': 'uespecs', 'command': 'ue_specs'},
        {'alias': 'Flu', 'command': 'flush_db'},
        # Add more aliases as needed
    ]
}

class SimulatorCLI(cmd.Cmd):
    
    def __init__(self, gNodeB_manager, cell_manager, sector_manager, ue_manager, network_load_manager, base_dir):
        super(SimulatorCLI, self).__init__()  # Correctly call the superclass initializer
        self.session = PromptSession()
        self.traffic_controller = TrafficController()
        self.base_dir = base_dir
        self.display_thread = None
        self.running = False
        self.term = Terminal()
        self.stop_event = threading.Event()
        # Assuming alias_config is defined
        self.aliases = self.generate_alias_mappings(alias_config)
        self.gNodeB_manager = gNodeB_manager
        self.cell_manager = cell_manager
        self.sector_manager = sector_manager
        self.ue_manager = UEManager.get_instance(base_dir)  # If UEManager.get_instance() is necessary, make sure it's called correctly
        self.network_load_manager = network_load_manager
        self.traffic_controller = TrafficController.get_instance() # # Assuming there's a way to get a TrafficController instance
        self.stop_event = Event()
        self.in_kpis_mode = False

        # Setup for prompt_toolkit completion
        commands = [cmd[3:] for cmd in dir(self) if cmd.startswith('do_')]
        self.completer = WordCompleter(commands + list(self.aliases.keys()), ignore_case=True)

    # cmdloop to use prompt_toolkit
    def cmdloop(self, intro=None):
        self.print_global_help()  # Display custom help menu at startup
        stop = None
        while not stop:
            try:
                line = self.session.prompt(self.prompt, style=cli_style, completer=self.completer)
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            except (KeyboardInterrupt, EOFError):
                print("Exiting.")
                break
            
    @staticmethod
    def generate_alias_mappings(config):
        """Generates a dictionary mapping aliases to commands."""
        mappings = {}
        for item in config['aliases']:
            mappings[item['alias']] = item['command']
        return mappings

    intro = "Welcome to the RAN Fusion Simulator CLI.\nType --help to list commands.\n"
    prompt ='Cli-host ' 

    def precmd(self, line):
        line = line.strip()
        if line == 'exit':
            return 'exit'  # Ensures that 'exit' command is recognized and processed
        if line in self.aliases:
            return self.aliases.get(line, line)
        else:
            return line
        
    def do_help(self, arg):
        if arg in ['--help', '-h', '']:
            super().do_help(None)
        else:
            super().do_help(arg)
################################################################################################################################ 
    def do_ue_list(self, arg):
        args = arg.split()
        page = 1
        page_size = 10  # Default number of items per page
        if len(args) == 2:
            try:
                page = int(args[0])
                page_size = int(args[1])
            except ValueError:
                print("Invalid page or page_size. Using defaults.")

        def display_page(page, page_size):
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            ue_ids = list(self.ue_manager.ues.keys())[start_index:end_index]
            total_ues = len(ue_ids)
            ues_to_display = ue_ids[start_index:end_index]

            table = PrettyTable()
            table.field_names = ["UE ID", "Service Type", "Throughput(MB)"]
            table.align = "l"
            table.border = True
            table.header = True
            table.header_style = "title"

            for ue_id in ues_to_display:
                ue = self.ue_manager.get_ue_by_id(ue_id)
                print(f"UE ID being passed to get_ue_by_id: {ue_id}")
                if ue:
                    throughput_mbps = ue.throughput / 1e6
                    table.add_row([ue.ID, ue.ServiceType, f"{throughput_mbps:.2f}"])
                    print(f"UE ID: {ue.ID}, Connected Cell: {ue.ConnectedCellID}, ...")

                else:
                    print(f"UE with ID {ue_id} not found.")
            print(table)
            total_pages = (total_ues // page_size) + (1 if total_ues % page_size > 0 else 0)
            print(f"Page {page} of {total_pages}")

        def refresh_data(stop_event):
            while not stop_event.is_set():
                os.system('cls' if os.name == 'nt' else 'clear')  # Clear the console
                display_page(page, page_size)  # Display the current page
                stop_event.wait(timeout=1)  # Refresh every 5 seconds

        # Initialize stop_event and display_thread
        stop_event = threading.Event()
        display_thread = threading.Thread(target=refresh_data, args=(stop_event,))

        try:
            display_thread.start()  # Start the refreshing thread

            input("Press Enter to stop refreshing...")  # Wait for user input to stop refreshing
        finally:
            stop_event.set()  # Signal the thread to stop
            display_thread.join()  # Wait for the thread to finish

        # After stopping the refresh, you can implement further actions or exit the command


############################################################################################################################## 
    def do_ue_log(self, arg):
        """Display UE (User Equipment) traffic logs with live updates."""
        print("Displaying UE traffic logs. Press Ctrl+C to return to the CLI.")

        def refresh_data(stop_event):
            while not stop_event.is_set():
                try:
                    # Clear the console for a fresh display
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print("Displaying UE traffic logs. Press Ctrl+C to return to the CLI.")
                    
                    # Initialize PrettyTable with column headers
                    table = PrettyTable(["UE ID", "Service Type", "Throughput (MB)", "Delay (ms)", "Jitter (%)", "Packet Loss Rate (%)"])
                    
                    # Fetch current UE instances
                    ue_instances = UE.get_ues()
                    
                    # Iterate over each UE instance to extract and display its attributes
                    for ue in ue_instances:
                        # Convert throughput from bytes to MB
                        throughput_mbps = ue.throughput / 1e6
                        
                        # Add a row to the table for each UE's traffic data
                        table.add_row([
                            ue.ID,  # UE ID
                            ue.ServiceType,  # Service Type
                            f"{throughput_mbps:.4f}",  # Throughput in MB
                            f"{ue.ue_delay}",  # Delay in ms
                            f"{ue.ue_jitter}%",  # Jitter in %
                            f"{ue.ue_packet_loss_rate*100}%"  # Packet Loss Rate in %
                        ])
                    print(table)
                    time.sleep(1)  # Refresh every 1 second
                except Exception as e:
                    print(f"Error displaying UE traffic logs: {e}")
                    break

        # Initialize stop_event and display_thread
        stop_event = threading.Event()
        display_thread = threading.Thread(target=refresh_data, args=(stop_event,))

        try:
            display_thread.start()  # Start the refreshing thread

            input("Press Enter to stop refreshing...")  # Wait for user input to stop refreshing
        finally:
            stop_event.set()  # Signal the thread to stop
            display_thread.join()  # Wait for the thread to finish
################################################################################################################################ 
    # Adjusted display_gnb_list method
    def display_gnb_list(self):
        term = Terminal()
        with term.cbreak(), term.hidden_cursor():
            while not self.stop_event.is_set():
                # Clear the screen before reprinting the updated table
                self.clear_screen(term)  # Make sure to pass 'term' here

                # Reconstruct and print the gNodeB table
                gNodeB_details_list = self.gNodeB_manager.list_all_gNodeBs_detailed()
                gNodeB_loads = self.network_load_manager.calculate_gNodeB_load()
                table = PrettyTable()
                table.field_names = ["gNodeB ID", "Latitude", "Longitude", "Coverage Radius", "Transmission Power", "Bandwidth", "Load %"]
                for gNodeB in gNodeB_details_list:
                    load_percentage = gNodeB_loads.get(gNodeB['id'], 0)
                    table.add_row([
                        gNodeB['id'],
                        gNodeB['latitude'],
                        gNodeB['longitude'],
                        gNodeB.get('coverage_radius', 'N/A'),
                        gNodeB.get('transmission_power', 'N/A'),
                        gNodeB.get('bandwidth', 'N/A'),
                        f"{load_percentage:.2f}%"
                    ])
                print(table)
                time.sleep(1)  # Refresh interval

    # Modification in the command method to start the automatic refresh mechanism
    def do_gnb_list(self, arg):
        """Displays the gNodeB list with automatic refresh."""
        print('Displaying gNodeB list. Press any key to stop...')

        # Initialize and start the display thread
        self.stop_event.clear()
        display_thread = threading.Thread(target=self.display_gnb_list)
        display_thread.start()

        # Wait for user input to stop the display
        with self.term.cbreak():
            self.term.inkey()

        # Signal the display thread to stop and wait for it to finish
        self.stop_event.set()
        display_thread.join()
        print(self.term.clear)  # Clear the screen after stopping
################################################################################################################################ 
    def clear_screen(self, term):
        """Clears the terminal screen."""
        print(term.home + term.clear, end='')
################################################################################################################################
    def display_cell_list(self):
        term = Terminal()
        with term.cbreak(), term.hidden_cursor():
            while not self.stop_event.is_set():
                # Use clear_screen instead of printing term.home + term.clear directly
                self.clear_screen(term)
    
                # Initialize PrettyTable with specific attributes
                table = PrettyTable()
                table.field_names = ["Cell ID", "Technology", "Status", "Active UEs", "Cell Load (%)"]
                table.align = "c"
                table.align["Cell ID"] = "l"
                table.title = "Cell List"
                table.header_style = "title"
                table.border = True
    
                # Fetch cell details
                cell_details_list = self.cell_manager.list_all_cells_detailed()
                for cell_detail in cell_details_list:
                    cell_id = cell_detail['id']
                    cell = self.cell_manager.get_cell(cell_id)
                    if cell is None:
                        continue
        
                    technology = cell_detail.get('technology', '5GNR')
                    status = f"{term.green}Active{term.normal}" if cell.IsActive else f"{term.yellow}Inactive{term.normal}"
                    active_ues = len(cell.ConnectedUEs)
                    cell_load_percentage = self.network_load_manager.calculate_cell_load(cell)
        
                    row = [
                        cell_id,
                        technology,
                        status,
                        str(active_ues),
                        f"{cell_load_percentage:.2f}%"
                    ]
                    table.add_row(row)
    
                print(table)
                time.sleep(1)
    
    def do_cell_list(self, arg):
        """Displays the cell list with live updates."""
        print('Displaying cell list. Press any key to stop...')

        # Initialize and start the display thread
        self.stop_event.clear()
        display_thread = threading.Thread(target=self.display_cell_list)
        display_thread.start()

        # Wait for user input to stop the display
        with self.term.cbreak():
            self.term.inkey()

        # Signal the display thread to stop and wait for it to finish
        self.stop_event.set()
        display_thread.join()
        print(self.term.clear)  # Clear the screen after stopping
################################################################################################################################ 
    def display_sector_list(self):
        term = Terminal()
        with term.cbreak(), term.hidden_cursor():
            while not self.stop_event.is_set():
                self.clear_screen(term)

                table = PrettyTable()
                table.field_names = ["Sector ID", "Cell ID", "Max UEs", "Active UEs", "Max Throughput", "Sector Load (%)"]
                table.align = "c"
                table.title = "Sector List"
                table.header_style = "title"
                table.border = True

                sector_list = self.sector_manager.list_all_sectors()
                for sector_info in sector_list:
                    sector_id = sector_info['sector_id']
                    sector = self.sector_manager.get_sector_by_id(sector_id)
                    if sector is None:
                        continue

                    status = f"{term.green}Active{term.normal}" if sector.is_active else f"{term.yellow}Inactive{term.normal}"
                    active_ues = len(sector.connected_ues)
                    sector_load_percentage = self.network_load_manager.calculate_sector_load(sector)

                    row = [
                        sector_id,
                        sector_info['cell_id'],
                        sector_info['capacity'],
                        active_ues,
                        sector_info['max_throughput'],
                        f"{sector_load_percentage:.2f}%"
                    ]
                    table.add_row(row)

                print(table)
                time.sleep(1)
    def do_sector_list(self, arg):
        print('Displaying sector list. Press any key to stop...')

        self.stop_event.clear()
        display_thread = threading.Thread(target=self.display_sector_list)
        display_thread.start()

        with self.term.cbreak():
            self.term.inkey()

        self.stop_event.set()
        display_thread.join()
        print(self.term.clear)  # This line will clear the screen after stopping the thread
################################################################################################################################
    def do_ue_specs(self, arg):
        """Displays specifications of all UEs with live updates."""
        print('Displaying UE specs. Press any key to stop...')

        def refresh_ue_specs(stop_event):
            while not stop_event.is_set():
                os.system('cls' if os.name == 'nt' else 'clear')  # Clear the console for Windows or Unix-based systems
                self.fetch_and_display_ue_specs()  # Fetch and display the current UE specs
                stop_event.wait(timeout=1)  # Refresh every second

        # Initialize stop_event and display_thread
        stop_event = threading.Event()
        display_thread = threading.Thread(target=refresh_ue_specs, args=(stop_event,))

        try:
            display_thread.start()  # Start the refreshing thread

            input("Press Enter to stop refreshing...")  # Wait for user input to stop refreshing
        finally:
            stop_event.set()  # Signal the thread to stop
            display_thread.join()  # Wait for the thread to finish

    def fetch_ue_instances(self):
        """
        Fetches current UE instances and formats them for display.
        
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a UE with its attributes.
        """
        ue_instances = UE.get_ues()  # Use the class method from the UE class to get all UE instances
        ue_list = []  # Initialize an empty list to hold formatted UE data

        # Iterate over each UE instance to extract and format its attributes
        for ue in ue_instances:
            ue_data = {
                'id': ue.ID,
                'Connected Cell ID': ue.ConnectedCellID,
                'Connected Sector ID': ue.ConnectedSector,
                'gNodeB ID': ue.gNodeB_ID,
                'Service Type': ue.ServiceType,
                'IMEI': ue.IMEI,
                'Signal Strength': ue.SignalStrength,
                'RAT': ue.RAT,
                'Max Bandwidth': ue.MaxBandwidth,
                'Throughput': ue.get_throughput(),
                'IP Address': ue.IP,
                'MAC Address': ue.MAC,
                'UE Jitter': ue.ue_jitter,
                'UE Packet Loss Rate': ue.ue_packet_loss_rate,
                'UE Delay': ue.ue_delay
            }
            ue_list.append(ue_data)  # Add the formatted UE data to the list

        return ue_list

    def fetch_and_display_ue_specs(self):
        ue_instances = self.fetch_ue_instances()  # Fetch current UE instances
        table = PrettyTable()
        table.field_names = ["Attribute"] + [f"{ue['id']}" for ue in ue_instances]

        attributes = [
            "Connected Cell ID", "Connected Sector ID", "gNodeB ID", 
            "Service Type", "IMEI", "Signal Strength", "RAT", "Max Bandwidth",
            "Throughput", "IP Address", "MAC Address", "UE Jitter",
            "UE Packet Loss Rate", "UE Delay"
        ]

        for attr in attributes:
            row = [attr] + [ue.get(attr, "N/A") for ue in ue_instances]
            table.add_row(row)

        print(table)
################################################################################################################################            
    def do_del_ue(self, line):
        from network.sector import global_ue_ids

        ue_id = line.strip().lower()  # Convert UE ID to lowercase for case-insensitive processing
        if not ue_id:
            print("Usage: del_ue <ue_id>")
            return

        print(f"Trying to delete UE {ue_id}")

        # Use UEManager to get the UE instance in a case-insensitive manner
        ue_manager = UEManager.get_instance(self.base_dir)

        # Use UEManager's delete_ue method to encapsulate the deletion logic
        try:
            if ue_manager.delete_ue(ue_id):
                print(f"UE {ue_id} has been successfully removed.")
            else:
                print(f"Failed to remove UE {ue_id}.")
        except Exception as e:
            print(f"Error removing UE: {e}")
################################################################################################################################
    def handle_command(command):
        # Assuming the command format is "add_ue ue <UE_ID>,<Sector_ID>,<Service_Type>"
            _, ue_id, sector_id, service_type = command.split()
            add_ue(ue_id, sector_id, service_type)

    def add_ue(ue_id, sector_id, service_type):
        # You would call a method here to handle the addition of the UE.
        # This method would need to be defined in a suitable class, such as UeManager.
        # It would involve creating a new UE instance with the specified parameters
        # and adding it to the specified sector.
        ue_config = {
            "ue_id": ue_id,
            "connected_sector": sector_id,
            "service_type": service_type
        }
        # Assuming UEManager is already instantiated and accessible
        ue_manager.create_ue(ue_config)
################################################################################################################################ 
    def do_kpis(self, arg):
        """
        Enter the KPIs submenu.
        """
        self.in_kpis_mode = not self.in_kpis_mode # Toggle KPIs mode
        if self.in_kpis_mode:
            init(autoreset=True)
            self.prompt = 'Cli-host ' 
        else:
            self.prompt = f'{Fore.GREEN}Cli-host{Style.RESET_ALL} '
        print("Entered KPIs submenu...")
################################################################################################################################
    def do_loadbalancing(self, arg):
        """
        call loadbalancing manually triggered by typing 'loadbalancing' in the CLI.the optimze the load of the each cell/sector
        """
        # Implement the logic call display load balancing information here.
        print("Displaying load balancing massagage...")

################################################################################################################################ 
    def print_global_help(self):
        if not self.in_kpis_mode:
            print(f"\n{Fore.GREEN}Global options:{ColoramaStyle.RESET_ALL}")
            print(f"  {Fore.GREEN}--help{Fore.RESET}        Show this help message and exit")
            print(f"\n{ColoramaStyle.BRIGHT}Available commands:{ColoramaStyle.RESET_ALL}")
            for command, description in [
                ('cell_list', 'List all cells in the network.'),
                ('gnb_list', 'List all gNodeBs in the network.'),
                ('sector_list', 'List all sectors in the network.'),
                ('ue_list', 'List all UEs (User Equipments) in the network.'),
                ('ue_log', 'Display UE traffic logs.'),
                ('ue_specs', 'Display UE specifications of ue in the network.'),
                ('del_ue', 'Delete ue from sector and database'),
                ('add_ue', 'add new ue based on current config file to the specific sector'),
                ('kpis', 'Display KPIs for the network.'),
                ('loadbalancing', 'Display load balancing information for the network.'),
                ('start_ue', 'Start the ue traffic.'),
                ('stop_ue', 'Stop the ue traffic.'),
                ('Flush Database', 'Delete all the information inside the InfluxDB database.'),
                ('exit', 'Exit the Simulator.')
            ]:
                print(f"  {Fore.CYAN}{command}{Fore.RESET} - {description}")
        else:
            # KPIs submenu help message
            print(f"\n{ColoramaStyle.BRIGHT}KPIs submenu commands:{ColoramaStyle.RESET_ALL}")
            for command, description in [
                ('ue_kpis', 'Display KPIs for User Equipments (UEs).'),
                ('exit', 'Return to the main menu.'),
            ]:
                print(f"  {Fore.CYAN}{command}{Fore.RESET} - {description}")
        print()

################################################################################################################################ 
    def do_stop_ue(self, arg):
        """Stop traffic generation for a specific UE."""
        if not arg:
            print("Please provide a UE ID.")
            return
        try:
            # Ensure the UE ID is in the correct format (e.g., "UE10")
            ue_id = f"UE{arg}"
            # Retrieve the UE object using the UE ID
            ue = UE.get_ue_instance_by_id(ue_id)
            if not ue:
                print(f"UE with ID {ue_id} not found.")
                return
            # Assuming there's a method in ue_manager to stop traffic for a UE
            self.traffic_controller.stop_ue_traffic(ue)
            print(f"Traffic generation for UE {ue.ID} has been stopped.")
        except Exception as e:
            print(f"Error stopping traffic for UE: {e}")

    def do_start_ue(self, arg):
        """Start traffic generation for a specific UE."""
        if not arg:
            print("Please provide a UE ID.")
            return
        try:
            # Ensure the UE ID is in the correct format (e.g., "UE10")
            ue_id = f"UE{arg}"
            # Retrieve the UE object using the UE ID
            ue = UE.get_ue_instance_by_id(ue_id)
            if not ue:
                print(f"UE with ID {ue_id} not found.")
                return
            # Call the start_ue_traffic method with the UE object
            self.traffic_controller.start_ue_traffic(ue)
            print(f"Traffic generation for UE {ue.ID} has been started.")
        except Exception as e:
            print(f"Error starting traffic for UE: {e}")
################################################################################################################################
    def complete(self, text, state):
        # Filter completions matching the text and return one by one
        results = [cmd for cmd in self.completions if cmd.startswith(text)] + [None]
        return results[state]

    def commands_with_aliases(self, text):
        # Include both commands and aliases that start with 'text'
        commands = [cmd[3:] for cmd in dir(self) if cmd.startswith('do_') and cmd[3:].startswith(text)]
        aliased_commands = [alias for alias, cmd in self.aliases.items() if alias.startswith(text)]
        return commands + aliased_commands

    def complete_default(self, text, line, begidx, endidx):
        # Implement your default auto-completion logic here, if any...
        return []

    def complete_gnb_list(self, text, line, begidx, endidx):
        # Assuming self.gNodeB_manager.gnbs is a list of gNodeB names
        if hasattr(self.gNodeB_manager, 'gnbs'):
            return [gnb for gnb in self.gNodeB_manager.gnbs if gnb.startswith(text)]
        return []

    # For alias 'gnb', just delegate to complete_gnb_list
    def complete_gnb(self, *args):
        return self.complete_gnb_list(*args)
    
    def complete_ue_log(self, text, line, begidx, endidx):
        # Since ue_log might not have specific arguments to complete, return an empty list
        # Or, return common log-related suggestions if applicable
        return []
    
    def complete_ulog(self, *args):
        return self.complete_ue_log(*args)
    
    def default(self, line):
        if line.strip() in ['--help', '-h']:
            self.do_help('')
        else:
            print("*** Unknown syntax:", line)

    def do_exit(self, arg):
        """Exit the simulator."""
        print("Exiting the simulator...")
        return True
#############################################################################################################
    def precmd(self, line):
        line = line.strip()
    
        if self.in_kpis_mode:
            if line == "exit":
                # Exit KPIs submenu
                self.in_kpis_mode = False
                self.prompt = 'Cli-host '  
                return ''  # Return empty string to prevent further processing
            elif line not in ['ue_kpis']:
                print("Invalid command in KPIs submenu. Available commands: 'ue_kpis', 'exit'")
                return ''  # Return empty string to prevent further processing
    
        elif line in self.aliases:
            return self.aliases.get(line, line)
        
        return line
#############################################################################################################
    def do_ue_kpis(self, arg):
        if not self.in_kpis_mode:
            print("UE KPIs command is only available in the KPIs submenu.") 
            return
    
        # Display KPIs
        print("Displaying UE KPIs...")
#############################################################################################################
    def do_flush_db(self, arg):
        """Flush Database: Delete all the information inside the InfluxDB database."""
        response = input("Are you sure you want to delete all the data in the database? (yes/no): ")
        if response.lower() == 'yes':
            db_manager = DatabaseManager.get_instance()
            success = db_manager.flush_all_data()  # This now returns True on success, False on failure
            if success:
                print("Database successfully flushed. Please run again!")
            else:
                print("Failed to flush the database.")  # Only print this if flushing fails
        else:
            print("Database flush canceled.")
#############################################################################################################