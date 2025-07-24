# camera_manager.py

# Imports
import cv2

class CameraManager:
    def __init__(self, camera_id=0):
        self.camera_id = camera_id # Default camera ID (0 for the first camera)
        self.cap = None # Video capture object

    # Start the camera
    # This method initializes the camera and starts capturing video.
    # Returns True if successful, False otherwise.
    def start_camera(self):
        self.cap = cv2.VideoCapture(self.camera_id) # Initialize the camera
        if not self.cap.isOpened(): 
            print(f"Error: Could not open video device {self.camera_id}.") # Error message if camera cannot be opened
            return False
        print(f"Camera {self.camera_id} started successfully.") # Confirmation message if camera starts successfully
        return True

    # Get a frame from the camera
    # This method reads a frame from the camera.
    # Returns the frame if successful, None if not.
    def get_frame(self):
        if self.cap and self.cap.isOpened():
            # print("CAMERA_MANAGER: Attempting to read frame...") # Attempt to read frame # For debugging
            ret, frame = self.cap.read()
            if not ret:
                print("CAMERA_MANAGER: self.cap.read() returned ret=False. Returning None.")
                return None
            # print("CAMERA_MANAGER: Frame read successfully.") # Frame read successfully # For debugging
            return frame
        else: # Added else for clarity
            print("CAMERA_MANAGER: cap is None or not opened in get_frame. Returning None.")
            return None
        
    # Release the camera
    # This method releases the camera resource.
    # It should be called when the camera is no longer needed. Such as when the application is closing.
    # It ensures that the camera is properly released to avoid resource leaks.
    def release_camera(self):
        if self.cap:
            self.cap.release()
            print(f"Camera {self.camera_id} released.")

    # Check if the camera is opened
    def is_opened(self):
        return self.cap is not None and self.cap.isOpened()

if __name__ == '__main__':
    
    # Test the CameraManager
    # This block is for testing the CameraManager class.
    cam_manager = CameraManager()
    if cam_manager.start_camera():
        while True:
            frame = cam_manager.get_frame()
            if frame is None:
                break
            
            cv2.imshow('Camera Test', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cam_manager.release_camera()
        cv2.destroyAllWindows()