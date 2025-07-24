# gesture_classifier.py
# This file is responsible for taking the raw hand landmark data from MediaPipe and
# interpreting it into a specific, named gesture template (like "OPEN_PALM" or "THUMB_POINTING_LEFT").
# It uses geometric calculations based on the positions of the landmarks.

# Imports
import mediapipe as mp
import math
import numpy as np

class GestureClassifier:
    def __init__(self):
        # Provides access to the MediaPipe Hand Landmarks (e.g., mp_hands.HandLandmark.WRIST)
        self.mp_hands = mp.solutions.hands
        
        # --- TUNING THRESHOLDS ---
        # These constants control the sensitivity of the gesture detection logic.
        
        # How far above the PIP joint a fingertip must be to be considered "strictly" up.
        # Used for very clear finger extension.
        self.FINGER_UP_Y_THRESHOLD_STRICT = 0.02
        
        # A value of 0 means the tip/pip must be strictly above the mcp
        self.FINGER_UP_Y_THRESHOLD_LOOSE = 0 
        
        # For thumb gestures, how far down the other fingers must be curled.
        self.THUMBS_UP_CURL_THRESHOLD = 0.01  
        
        # How far above the MCP joint a fingertip must be to be considered "generally" up.
        # Converts the MediaPipe landmarks object into a simple NumPy array for easier calculations.
    def _get_landmark_list(self, hand_landmarks):
        # MediaPipe's 'hand_landmarks' is an object. A NumPy array is much better for vector math for classifying gestures.
        return np.array([(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark])

    # Calculates the Euclidean distance between two 3D points. 
    # Euclidean distance is needed because the landmarks are in a 3D space, and we need it to calculate between landmark pairs.
    def _calculate_distance(self, p1, p2):
        p1_arr = np.array(p1); p2_arr = np.array(p2)
        return math.sqrt(np.sum((p1_arr - p2_arr)**2))

    # Calculates a reference distance to normalize thresholds by hand size.
    # A hand further from the camera will appear smaller, and its landmark distances will be smaller.
    # Using this reference helps our thresholds adapt to the hand's distance from the camera.
    # Make it more robust to small errors in landmark detection, regardless of hand size or distance.
    def _get_wrist_to_middle_mcp_dist(self, lm_array):
        wrist = lm_array[self.mp_hands.HandLandmark.WRIST]
        middle_mcp = lm_array[self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
        dist = self._calculate_distance(wrist, middle_mcp)
        # If the distance is too small (e.g., error in detection), return a safe default.
        return dist if dist > 0.01 else 0.15

    # Determines which of the five fingers are UP.
    # Returns a list of 5 booleans (0 or 1) and the total count.
    # 0 for close, 1 for up.
    def _count_fingers_up(self, lm_array, hand_scale_ref):
        # [0/1, 0/1, 0/1, 0/1, 0/1] = [Thumb, Index, Middle, Ring, Pinky]
        fingers_up_status = [0, 0, 0, 0, 0]
        
        # Get the integer indices for landmark types for easier looping and access. 
        # ids = indices of the landmarks in the MediaPipe HandLandmark enum.
        tip_ids = [self.mp_hands.HandLandmark.THUMB_TIP, self.mp_hands.HandLandmark.INDEX_FINGER_TIP,
                   self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP, self.mp_hands.HandLandmark.RING_FINGER_TIP,
                   self.mp_hands.HandLandmark.PINKY_TIP]
        pip_ids = [self.mp_hands.HandLandmark.THUMB_IP, self.mp_hands.HandLandmark.INDEX_FINGER_PIP,
                   self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP, self.mp_hands.HandLandmark.RING_FINGER_PIP,
                   self.mp_hands.HandLandmark.PINKY_PIP]
        mcp_ids = [self.mp_hands.HandLandmark.THUMB_MCP, self.mp_hands.HandLandmark.INDEX_FINGER_MCP,
                   self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP, self.mp_hands.HandLandmark.RING_FINGER_MCP,
                   self.mp_hands.HandLandmark.PINKY_MCP]

        # --- THUMB CHECK ---
        # This logic determines if the thumb is "out" and thus a candidate for a gesture.
        # It checks the thumb's tip position relative to the index finger's base (MCP).
        thumb_tip_x = lm_array[tip_ids[0]][0]
        index_mcp_x = lm_array[mcp_ids[1]][0]
        pinky_mcp_x = lm_array[mcp_ids[4]][0]

        # First, we determine the hand's orientation on the screen. The view is mirrored for the user.
        # A right hand is defined as having its index finger's base (MCP) at a smaller X-coordinate
        # This helps the program know exactly what hand the users is showing.
        # X-coordinate than its pinky finger base. A left hand is the opposite.
        
        # If the index finger's MCP is to the left of the pinky MCP, it's a right hand.
        if index_mcp_x < pinky_mcp_x: 
            # For a right hand, the thumb is "out" if its tip is to the left (smaller X) of the index base.
            if thumb_tip_x < index_mcp_x: fingers_up_status[0] = 1
        else:
            # For a left hand, the thumb is "out" if its tip is to the right (larger X) of the index base.
            if thumb_tip_x > index_mcp_x: fingers_up_status[0] = 1

        # --- Other Four Fingers check ---
        
        # We loop through the index, middle, ring, and pinky fingers.
        for i in range(1, 5):
            finger_tip_y = lm_array[tip_ids[i]][1]
            finger_pip_y = lm_array[pip_ids[i]][1]
            finger_mcp_y = lm_array[mcp_ids[i]][1]
            
            # Scale the threshold based on the hand's size/distance.
            scaled_strict_thresh = self.FINGER_UP_Y_THRESHOLD_STRICT * (hand_scale_ref / 0.15)
            scaled_loose_thresh = self.FINGER_UP_Y_THRESHOLD_LOOSE * (hand_scale_ref / 0.15)
            
            
            # Condition 1: The finger is very straight (tip is clearly above the middle joint).
            cond1_extended = finger_tip_y < finger_pip_y - scaled_strict_thresh
            
            # Condition 2: The finger is generally up (tip is above the base knuckle).
            # This is more lenient and allows for slightly bent fingers.
            cond2_generally_up = finger_tip_y < lm_array[mcp_ids[i]][1]
            cond2_generally_up = finger_tip_y < finger_mcp_y - scaled_loose_thresh and \
                                 finger_pip_y < finger_mcp_y - scaled_loose_thresh
            
            # If either condition is met, the finger is counted as "up".
            if cond1_extended or cond2_generally_up:
                fingers_up_status[i] = 1
        
        # Count how many fingers are up.
        # This is the sum of the list, where each 1 represents an up finger.
        total_fingers = sum(fingers_up_status)
        return fingers_up_status, total_fingers

    # Takes MediaPipe hand landmarks and returns a string key for the recognized gesture.
    # e.g., "OPEN_PALM", "THUMB_POINTING_LEFT", "POINT_UP".
    def classify(self, hand_landmarks):
        
        # If no hand is detected, return "NO_HAND" immediately.
        if not hand_landmarks: 
            return "NO_HAND"
        
        # --- Data Preparation ---
        lm_array = self._get_landmark_list(hand_landmarks)
        hand_scale_ref = self._get_wrist_to_middle_mcp_dist(lm_array)
        fingers_status, total_fingers = self._count_fingers_up(lm_array, hand_scale_ref)
        gesture_key = "UNKNOWN_GESTURE" # Default value
        
        # Get landmark indices again for use in this method
        tip_ids = [self.mp_hands.HandLandmark.THUMB_TIP, self.mp_hands.HandLandmark.INDEX_FINGER_TIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP, self.mp_hands.HandLandmark.RING_FINGER_TIP, self.mp_hands.HandLandmark.PINKY_TIP]
        pip_ids = [self.mp_hands.HandLandmark.THUMB_IP, self.mp_hands.HandLandmark.INDEX_FINGER_PIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP, self.mp_hands.HandLandmark.RING_FINGER_PIP, self.mp_hands.HandLandmark.PINKY_PIP]
        mcp_ids = [self.mp_hands.HandLandmark.THUMB_MCP, self.mp_hands.HandLandmark.INDEX_FINGER_MCP, self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP, self.mp_hands.HandLandmark.RING_FINGER_MCP, self.mp_hands.HandLandmark.PINKY_MCP]

        # --- GESTURE CLASSIFICATION LOGIC ---
        # The logic checks for the most specific gestures first to avoid misclassification.

        # 1. Check for THUMB POINTING gestures
        # This gesture is specific: exactly one finger (the thumb) must be up.
        if total_fingers == 1 and fingers_status[0] == 1:
            # To be sure it's a thumb gesture, we also check that the other fingers are curled.
            scaled_curl_thresh = self.THUMBS_UP_CURL_THRESHOLD * (hand_scale_ref / 0.15)
            index_closed = lm_array[tip_ids[1]][1] > lm_array[pip_ids[1]][1] + scaled_curl_thresh
            middle_closed = lm_array[tip_ids[2]][1] > lm_array[pip_ids[2]][1] + scaled_curl_thresh
            ring_closed = lm_array[tip_ids[3]][1] > lm_array[pip_ids[3]][1] + scaled_curl_thresh
            pinky_closed = lm_array[tip_ids[4]][1] > lm_array[pip_ids[4]][1] + scaled_curl_thresh

            if index_closed and middle_closed and ring_closed and pinky_closed:
                # If conditions are met, determine the direction the thumb is pointing.
                # Create a vector for the hand's "up" direction (wrist to middle knuckle).
                wrist_pt = lm_array[self.mp_hands.HandLandmark.WRIST][:2]
                middle_mcp_pt = lm_array[self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP][:2]
                hand_up_vector = middle_mcp_pt - wrist_pt

                # Create a vector for the thumb's direction (base to tip).
                thumb_mcp_pt = lm_array[self.mp_hands.HandLandmark.THUMB_MCP][:2]
                thumb_tip_pt = lm_array[self.mp_hands.HandLandmark.THUMB_TIP][:2]
                thumb_vector = thumb_tip_pt - thumb_mcp_pt
                
                # The 2D cross product tells us the orientation of the thumb vector relative to the hand vector.
                cross_product = np.cross(hand_up_vector, thumb_vector)
                
                # Because the camera view is mirrored, the signs (> and <) are swapped.
                if cross_product > 0.005: # Positive result means thumb is pointing to the screen's right.
                    gesture_key = "THUMB_POINTING_RIGHT"
                elif cross_product < -0.005: # Negative result means thumb is pointing to the screen's left.
                    gesture_key = "THUMB_POINTING_LEFT"
                # If cross product is near zero, thumb is pointing up. We ignore this gesture.
                
        # 2. Check for OPEN PALM (STOP command)
        # This is a less specific gesture, so we check it after the more specific ones.
        # Less specific because it can be confused with other gestures if not careful.
        # If 4 or 5 fingers are up, we classify it as an open palm.
        if gesture_key == "UNKNOWN_GESTURE" and total_fingers >= 4:
            gesture_key = "OPEN_PALM"
        
        # 3. Check for POINT UP (FORWARD command)
        # This is a very specific finger combination: [0, 1, 0, 0, 0]
        # This is a very specific check that ensures only the index finger is extended.
        if gesture_key == "UNKNOWN_GESTURE" and fingers_status == [0,1,0,0,0]:
            gesture_key = "POINT_UP"

        # 4. Check for PEACE SIGN (BACKWARD command)
        # This is also a very specific finger combination: [0, 1, 1, 0, 0]
        # This ensures only the index and middle fingers are extended.
        if gesture_key == "UNKNOWN_GESTURE" and fingers_status == [0,1,1,0,0]:
            gesture_key = "PEACE"

        # If none of the above conditions were met, gesture_key remains "UNKNOWN_GESTURE".
        return gesture_key