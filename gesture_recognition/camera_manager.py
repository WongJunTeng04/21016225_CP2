import cv2

class CameraManager:
    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.cap = None

    def start_camera(self):
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            print(f"Error: Could not open video device {self.camera_id}.")
            return False
        print(f"Camera {self.camera_id} started successfully.")
        return True

    # def get_frame(self):
    #     if self.cap and self.cap.isOpened():
    #         ret, frame = self.cap.read()
    #         if not ret:
    #             print("Error: Can't receive frame (stream end?).")
    #             return None
    #         return frame
    #     return None

    def get_frame(self):
        if self.cap and self.cap.isOpened():
            # print("CAMERA_MANAGER: Attempting to read frame...") # Verbose
            ret, frame = self.cap.read()
            if not ret:
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                print("CAMERA_MANAGER: self.cap.read() returned ret=False. Returning None.")
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                return None
            # print("CAMERA_MANAGER: Frame read successfully.") # Verbose
            return frame
        else: # Added else for clarity
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("CAMERA_MANAGER: cap is None or not opened in get_frame. Returning None.")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            return None
        
    def release_camera(self):
        if self.cap:
            self.cap.release()
            print(f"Camera {self.camera_id} released.")

    def is_opened(self):
        return self.cap is not None and self.cap.isOpened()

if __name__ == '__main__':
    # Simple test for CameraManager
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