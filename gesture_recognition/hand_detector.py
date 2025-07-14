import cv2
import mediapipe as mp
import time

# To detect hands using MediaPipe
class HandDetector:
    def __init__(self, static_mode=False, max_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.5):
        self.static_mode = static_mode
        self.max_hands = max_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=self.static_mode,
            max_num_hands=self.max_hands,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.results = None

    # Find the hands in the given RGB image.
    def find_hands(self, image_rgb):
        """
        Processes an RGB image to find hand landmarks.
        Returns the processed results object from MediaPipe.
        """
        image_rgb.flags.writeable = False # To improve performance
        self.results = self.hands.process(image_rgb)
        image_rgb.flags.writeable = True
        return self.results

    # Draw the landmarks 
    def draw_landmarks(self, image_bgr, hand_landmarks):
        """Draws landmarks and connections on a BGR image."""
        self.mp_drawing.draw_landmarks(
            image_bgr,
            hand_landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_drawing_styles.get_default_hand_landmarks_style(),
            self.mp_drawing_styles.get_default_hand_connections_style()
        )
        return image_bgr

    # Get the landmarks and handedness of the detected hands.
    # Returns None if no hands are detected.
    # If hands are detected, returns a tuple of (multi_hand_landmarks, multi_handedness).
    # multi_hand_landmarks is a list of landmarks for each detected hand.
    def get_landmarks(self):
        """Returns multi_hand_landmarks and multi_handedness if hands are detected."""
        if self.results and self.results.multi_hand_landmarks:
            return self.results.multi_hand_landmarks, self.results.multi_handedness
        return None, None

    def close(self):
        self.hands.close()

if __name__ == '__main__':
    from camera_manager import CameraManager

    cam = CameraManager()
    detector = HandDetector(max_hands=1)

    if not cam.start_camera():
        exit()

    prev_time = 0
    while cam.is_opened():
        frame_bgr = cam.get_frame()
        if frame_bgr is None:
            break

        # Flip and convert to RGB for MediaPipe
        frame_bgr_flipped = cv2.flip(frame_bgr, 1)
        frame_rgb = cv2.cvtColor(frame_bgr_flipped, cv2.COLOR_BGR2RGB)

        results = detector.find_hands(frame_rgb)
        
        # Convert back to BGR for display if needed (detector doesn't modify input image for drawing directly)
        display_image = frame_bgr_flipped.copy() # Work on a copy

        landmarks_list, handedness_list = detector.get_landmarks()
        if landmarks_list:
            for i, hand_landmarks in enumerate(landmarks_list):
                display_image = detector.draw_landmarks(display_image, hand_landmarks)
                # handedness = handedness_list[i].classification[0].label
                # print(f"Handedness: {handedness}")

        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        cv2.putText(display_image, f"FPS: {int(fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('Hand Detection Test', display_image)
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    detector.close()
    cam.release_camera()
    cv2.destroyAllWindows()