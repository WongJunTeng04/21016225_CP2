import json
import os

class ActionMapper:
    def __init__(self, config_file_path="config/gestures_config.json"):
        # Adjust path relative to where this module might be imported from,
        # or use an absolute path, or pass it during instantiation.
        # For simplicity, assuming config is relative to project root.
        
        # Get the directory of the current script (action_mapper.py)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to gesture_recognition, then up another to MobileRobotUX (project root)
        project_root = os.path.dirname(current_dir)
        self.config_path = os.path.join(project_root, config_file_path)
        
        self.gesture_actions = self._load_config()

    # Load Command
    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                actions = json.load(f)
                print(f"Loaded gesture config from: {self.config_path}")
                return actions
        except FileNotFoundError:
            print(f"Error: Gestures config file not found at {self.config_path}")
            # Return some default or raise an error
            return {"FALLBACK_ACTION": "STOP"} 
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {self.config_path}")
            return {"FALLBACK_ACTION": "STOP"}

    # Get Command
    def get_command(self, gesture_key):
        """
        Maps a gesture key (e.g., "FIST") to a robot command string.
        """
        return self.gesture_actions.get(gesture_key, "UNKNOWN_COMMAND") # Default if key not found

if __name__ == '__main__':
    # Test ActionMapper
    # Ensure gestures_config.json is in MobileRobotUX/config/
    mapper = ActionMapper(config_file_path="config/gestures_config.json") 
    # print(f"Command for OPEN_PALM: {mapper.get_command('OPEN_PALM')}")
    # print(f"Command for FIST: {mapper.get_command('FIST')}")
    # print(f"Command for MADE_UP_GESTURE: {mapper.get_command('MADE_UP_GESTURE')}")