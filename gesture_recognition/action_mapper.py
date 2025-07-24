# action_mapper.py

# Imports
import json
import os

class ActionMapper:
    def __init__(self, config_file_path="config/gestures_config.json"): # Path of the config file
        current_dir = os.path.dirname(os.path.abspath(__file__)) # Get the directory of this file
        project_root = os.path.dirname(current_dir) # Get the project root directory
        self.config_path = os.path.join(project_root, config_file_path) # Construct the full path to the config file
        # Done for more robust path handling
        
        self.gesture_actions = self._load_config() # Load the gesture actions from the config file

    # Load Command (From the gesture config file)
    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                actions = json.load(f) # Load the JSON config file
                print(f"Loaded gesture config from: {self.config_path}") # Confirmation message
                return actions # Return the loaded actions
        # Handle file not found
        except FileNotFoundError:
            print(f"Error: Gestures config file not found at {self.config_path}") # Handle file not found # Show error message
            # Return some default or raise an error
            return {"FALLBACK_ACTION": "STOP"} # Stop the robot if config file not found / Default action
        # Handle JSON decode error
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {self.config_path}") # Handle JSON decode error
            return {"FALLBACK_ACTION": "STOP"} # Stop the robot if config is invalid / Default action

    # Get Command (Maps a gesture key (e.g., "FIST") to a robot command string.)
    def get_command(self, gesture_key):
        return self.gesture_actions.get(gesture_key, "UNKNOWN_COMMAND") # Default if key not found