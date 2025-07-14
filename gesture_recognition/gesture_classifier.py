# gesture_classifier.py
# Import necessary libraries
import mediapipe as mp
import math
import numpy as np

# GestureClassifier class for classifying hand gestures based on MediaPipe landmarks
# This class uses MediaPipe's hand landmarks to determine the gesture being performed by the user.
# It includes methods for counting fingers, checking conditions for specific gestures,
# and classifying the gesture based on the landmarks detected.

class GestureClassifier:
    #Initializes the GestureClassifier with MediaPipe
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.FINGER_UP_Y_THRESHOLD_STRICT = 0.02
        self.FINGER_UP_Y_THRESHOLD_LOOSE = 0
        # For X outwards check, relative to thumb's OWN MCP.
        # Right hand: tip must be to the left of MCP (negative diff). Threshold is negative.
        # Left hand: tip must be to the right of MCP (positive diff). Threshold is positive.
        self.THUMB_X_OUTWARDS_MCP_THRESHOLD_RIGHT = -0.02 # Tip X < MCP_X - threshold_abs
        self.THUMB_X_OUTWARDS_MCP_THRESHOLD_LEFT = 0.02  # Tip X > MCP_X + threshold_abs
        self.THUMB_UP_Y_VS_MCP_THRESHOLD = 0.03 # Tip must be above MCP by this (scaled)
        self.FINGER_CURL_Y_MCP_THRESHOLD = 0.015
        self.THUMB_ACROSS_X_MARGIN = 0.03
        self.THUMB_Y_ALIGN_MCP_FACTOR = 0.8
        self.POINTING_OTHER_FINGERS_DOWN_Y_THRESHOLD = 0.02
        self.THUMBS_UP_CURL_THRESHOLD = 0.01 # Other fingers tip Y > PIP Y + threshold (more curled)

    # Initializes the MediaPipe Hands solution with default parameters
    def _get_landmark_list(self, hand_landmarks):
        return np.array([(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark])

    def _calculate_distance(self, p1, p2):
        p1_arr = np.array(p1); p2_arr = np.array(p2)
        return math.sqrt(np.sum((p1_arr - p2_arr)**2))

    # Calculates the distance from wrist to middle finger MCP (base knuckle)
    # Returns a default value if the distance is too small (indicating a potential error)
    # This is used as a reference scale for finger counting and gesture classification.
    # If the distance is less than 0.01, it returns a default value of 0.15.
    # This helps avoid division by zero or very small values in further calculations
    # and ensures that the scale reference is reasonable for gesture classification.
    # This is particularly useful for robust finger counting and gesture detection.
    # The default value of 0.15 is chosen based on typical hand sizes and distances
    # between the wrist and middle finger MCP in a normal hand.
    # If the distance is greater than 0.01, it returns the actual distance.
    # This allows the classifier to adapt to different hand sizes and positions.
    # If the distance is too small, it assumes a default hand scale reference.
    # This helps maintain consistent gesture classification across different hand sizes.
    def _get_wrist_to_middle_mcp_dist(self, lm_array):
        wrist = lm_array[self.mp_hands.HandLandmark.WRIST]
        middle_mcp = lm_array[self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
        dist = self._calculate_distance(wrist, middle_mcp)
        return dist if dist > 0.01 else 0.15

    # Counts the number of fingers that are "up" based on MediaPipe landmarks.
    def _count_fingers_up_robust(self, lm_array, handedness_str, hand_scale_ref):
        fingers_up_status = [0, 0, 0, 0, 0]
        tip_ids = [self.mp_hands.HandLandmark.THUMB_TIP, self.mp_hands.HandLandmark.INDEX_FINGER_TIP,
                   self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP, self.mp_hands.HandLandmark.RING_FINGER_TIP,
                   self.mp_hands.HandLandmark.PINKY_TIP]
        pip_ids = [self.mp_hands.HandLandmark.THUMB_IP, self.mp_hands.HandLandmark.INDEX_FINGER_PIP,
                   self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP, self.mp_hands.HandLandmark.RING_FINGER_PIP,
                   self.mp_hands.HandLandmark.PINKY_PIP]
        mcp_ids = [self.mp_hands.HandLandmark.THUMB_MCP, self.mp_hands.HandLandmark.INDEX_FINGER_MCP,
                   self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP, self.mp_hands.HandLandmark.RING_FINGER_MCP,
                   self.mp_hands.HandLandmark.PINKY_MCP]

        # --- Thumb ---
        thumb_tip = lm_array[tip_ids[0]]
        thumb_mcp = lm_array[mcp_ids[0]]

        # Y-condition: Thumb tip is above its MCP (base knuckle)
        scaled_thumb_y_mcp_thresh = self.THUMB_UP_Y_VS_MCP_THRESHOLD * (hand_scale_ref / 0.15)
        is_thumb_tip_above_mcp = thumb_tip[1] < thumb_mcp[1] - scaled_thumb_y_mcp_thresh

        # X-condition: Thumb tip is somewhat outwards from its MCP
        is_thumb_x_outwards_from_mcp = False
        if handedness_str == "Right":
            scaled_x_thresh = self.THUMB_X_OUTWARDS_MCP_THRESHOLD_RIGHT * (hand_scale_ref / 0.15) # Negative
            is_thumb_x_outwards_from_mcp = thumb_tip[0] < thumb_mcp[0] + scaled_x_thresh # Tip_X < MCP_X - abs_thresh
        elif handedness_str == "Left":
            scaled_x_thresh = self.THUMB_X_OUTWARDS_MCP_THRESHOLD_LEFT * (hand_scale_ref / 0.15) # Positive
            is_thumb_x_outwards_from_mcp = thumb_tip[0] > thumb_mcp[0] + scaled_x_thresh # Tip_X > MCP_X + abs_thresh
        
        # print(f"DEBUG_THUMB_COUNT: Hand: {handedness_str}, TipY:{thumb_tip[1]:.3f}, McpY:{thumb_mcp[1]:.3f} -> AboveMCP: {is_thumb_tip_above_mcp} (Thresh: {scaled_thumb_y_mcp_thresh:.3f})")
        # print(f"DEBUG_THUMB_COUNT: TipX:{thumb_tip[0]:.3f}, McpX:{thumb_mcp[0]:.3f} -> X_Outwards: {is_thumb_x_outwards_from_mcp} (ThreshR: {self.THUMB_X_OUTWARDS_MCP_THRESHOLD_RIGHT * (hand_scale_ref / 0.15):.3f}, ThreshL: {self.THUMB_X_OUTWARDS_MCP_THRESHOLD_LEFT * (hand_scale_ref / 0.15):.3f})")

        if is_thumb_tip_above_mcp and is_thumb_x_outwards_from_mcp:
            fingers_up_status[0] = 1
            # print("DEBUG_THUMB_COUNT: Thumb counted as UP.")
            
        # else: # Add this else for debugging if thumb is not counted up
            # print(f"DEBUG_THUMB_COUNT: Thumb counted as DOWN. AboveMCP={is_thumb_tip_above_mcp}, XOutwards={is_thumb_x_outwards_from_mcp}")

        # --- Other Four Fingers --- 
        for i in range(1, 5):
            finger_tip_y = lm_array[tip_ids[i]][1]; finger_pip_y = lm_array[pip_ids[i]][1]; finger_mcp_y = lm_array[mcp_ids[i]][1]
            scaled_strict_thresh = self.FINGER_UP_Y_THRESHOLD_STRICT * (hand_scale_ref / 0.15)
            scaled_loose_thresh = self.FINGER_UP_Y_THRESHOLD_LOOSE * (hand_scale_ref / 0.15) # Note: LOOSE is 0, so scaled_loose_thresh is also 0
            cond1_extended = finger_tip_y < finger_pip_y - scaled_strict_thresh
            # For cond2_generally_up, if scaled_loose_thresh is 0, it becomes tip_y < mcp_y AND pip_y < mcp_y
            cond2_generally_up = finger_tip_y < finger_mcp_y - scaled_loose_thresh and \
                                 finger_pip_y < finger_mcp_y - scaled_loose_thresh 
            if cond1_extended or cond2_generally_up:
                fingers_up_status[i] = 1
        
        total_fingers = sum(fingers_up_status)
        return fingers_up_status, total_fingers

    # Classifies the gesture based on the hand landmarks and handedness.
    # It uses the landmark positions to determine if the gesture is a thumbs up, open palm,
    # fist, point up, peace sign, or three fingers up.
    # It returns a string representing the classified gesture.
    # If no hand landmarks are provided, it returns "NO_HAND".
    # The classification is based on the positions of the fingertips and their relationships
    # to the base knuckles (MCPs) and other fingers.
    def classify(self, hand_landmarks, handedness_str):
        if not hand_landmarks: return "NO_HAND"
        lm_array = self._get_landmark_list(hand_landmarks)
        hand_scale_ref = self._get_wrist_to_middle_mcp_dist(lm_array)
        fingers_status, total_fingers = self._count_fingers_up_robust(lm_array, handedness_str, hand_scale_ref)
        gesture_key = "UNKNOWN_GESTURE"
        
        print(f"Classify - Hand: {handedness_str}, Fingers: {fingers_status}, Total: {total_fingers}, ScaleRef: {hand_scale_ref:.3f}")

        tip_ids = [self.mp_hands.HandLandmark.THUMB_TIP, self.mp_hands.HandLandmark.INDEX_FINGER_TIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP, self.mp_hands.HandLandmark.RING_FINGER_TIP, self.mp_hands.HandLandmark.PINKY_TIP]
        pip_ids = [self.mp_hands.HandLandmark.THUMB_IP, self.mp_hands.HandLandmark.INDEX_FINGER_PIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP, self.mp_hands.HandLandmark.RING_FINGER_PIP, self.mp_hands.HandLandmark.PINKY_PIP]
        mcp_ids = [self.mp_hands.HandLandmark.THUMB_MCP, self.mp_hands.HandLandmark.INDEX_FINGER_MCP, self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP, self.mp_hands.HandLandmark.RING_FINGER_MCP, self.mp_hands.HandLandmark.PINKY_MCP]

        # --- THUMBS UP ---
        if fingers_status[0] == 1 and sum(fingers_status[1:]) == 0:
            # print("GC_DEBUG: Candidate for THUMBS_UP (Initial check: thumb up, others down by count).")
            scaled_thumbs_up_curl_thresh = self.THUMBS_UP_CURL_THRESHOLD * (hand_scale_ref / 0.15)
            # Tip Y > PIP Y + thresh means tip is BELOW pip by at least threshold amount
            index_closed = lm_array[tip_ids[1]][1] > lm_array[pip_ids[1]][1] + scaled_thumbs_up_curl_thresh
            middle_closed = lm_array[tip_ids[2]][1] > lm_array[pip_ids[2]][1] + scaled_thumbs_up_curl_thresh
            ring_closed = lm_array[tip_ids[3]][1] > lm_array[pip_ids[3]][1] + scaled_thumbs_up_curl_thresh
            pinky_closed = lm_array[tip_ids[4]][1] > lm_array[pip_ids[4]][1] + scaled_thumbs_up_curl_thresh
            # print(f"GC_DEBUG_THUMBS_UP_CURL: I:{index_closed}, M:{middle_closed}, R:{ring_closed}, P:{pinky_closed}")
            if index_closed and middle_closed and ring_closed and pinky_closed:
                # print("GC_DEBUG: THUMBS_UP confirmed by curled fingers.")
                if handedness_str == "Right": gesture_key = "THUMB_UP_RIGHT"
                elif handedness_str == "Left": gesture_key = "THUMB_UP_LEFT"
                else: gesture_key = "THUMB_UP"
        
        # --- OPEN PALM ---
        if gesture_key == "UNKNOWN_GESTURE" and total_fingers >= 4:
            index_tip = lm_array[tip_ids[1]]; middle_tip = lm_array[tip_ids[2]]; ring_tip = lm_array[tip_ids[3]]
            dist_index_middle = abs(index_tip[0] - middle_tip[0]); dist_middle_ring = abs(middle_tip[0] - ring_tip[0])
            min_spread_threshold = 0.03 * (hand_scale_ref / 0.15); is_spread = dist_index_middle > min_spread_threshold and dist_middle_ring > min_spread_threshold
            if total_fingers == 5 or (total_fingers >= 4 and is_spread): gesture_key = "OPEN_PALM"


        # # --- FIST ---
        # if gesture_key == "UNKNOWN_GESTURE" and total_fingers <= 1: 
        #     print("GC_DEBUG: Candidate for FIST (total_fingers <= 1).")
        #     scaled_curl_thresh_fist = self.FINGER_CURL_Y_MCP_THRESHOLD * (hand_scale_ref / 0.15)
        #     index_curled = lm_array[tip_ids[1]][1] > lm_array[mcp_ids[1]][1] + scaled_curl_thresh_fist
        #     middle_curled = lm_array[tip_ids[2]][1] > lm_array[mcp_ids[2]][1] + scaled_curl_thresh_fist
        #     ring_curled = lm_array[tip_ids[3]][1] > lm_array[mcp_ids[3]][1] + scaled_curl_thresh_fist
        #     pinky_curled = lm_array[tip_ids[4]][1] > lm_array[mcp_ids[4]][1] + scaled_curl_thresh_fist
            
        #     if index_curled and middle_curled and ring_curled and pinky_curled:
        #         # Now check thumb for fist (if fingers_status[0] was 1, thumb needs to be tucked)
        #         if fingers_status[0] == 0: # Thumb already counted as down by robust counter
        #             gesture_key = "FIST"
        #         elif fingers_status[0] == 1: # Thumb was counted as up, check if it's tucked for a fist
        #             thumb_tip = lm_array[tip_ids[0]]; index_mcp = lm_array[mcp_ids[1]]; pinky_mcp = lm_array[mcp_ids[4]]
        #             scaled_thumb_y_align_fist = abs(index_mcp[1] - lm_array[pip_ids[1]][1]) * self.THUMB_Y_ALIGN_MCP_FACTOR
        #             thumb_y_tucked_fist = thumb_tip[1] > index_mcp[1] - scaled_thumb_y_align_fist
        #             scaled_thumb_x_margin_fist = self.THUMB_ACROSS_X_MARGIN * (hand_scale_ref / 0.15)
        #             thumb_x_across_fist = False
        #             if handedness_str == "Right": thumb_x_across_fist = (index_mcp[0] + scaled_thumb_x_margin_fist > thumb_tip[0] > pinky_mcp[0] - scaled_thumb_x_margin_fist)
        #             elif handedness_str == "Left": thumb_x_across_fist = (pinky_mcp[0] - scaled_thumb_x_margin_fist < thumb_tip[0] < index_mcp[0] + scaled_thumb_x_margin_fist)
        #             dist_thumb_middle_pip = self._calculate_distance(thumb_tip, lm_array[pip_ids[2]])
        #             thumb_close_to_palm_fist = dist_thumb_middle_pip < (0.07 * (hand_scale_ref / 0.15))
        #             if (thumb_x_across_fist or thumb_close_to_palm_fist) and thumb_y_tucked_fist:
        #                 gesture_key = "FIST"
        #     # if gesture_key == "FIST": print("GC_DEBUG: FIST confirmed.")
        
        # --- POINT UP ---
        if gesture_key == "UNKNOWN_GESTURE" and \
           (fingers_status == [0,1,0,0,0] or \
           (fingers_status[0] == 1 and fingers_status[1] == 1 and sum(fingers_status[2:]) == 0)):
            # print("GC_DEBUG: Candidate for POINT_UP.")
            scaled_pointing_down_thresh = self.POINTING_OTHER_FINGERS_DOWN_Y_THRESHOLD * (hand_scale_ref / 0.15)
            middle_down = lm_array[tip_ids[2]][1] > lm_array[pip_ids[2]][1] + scaled_pointing_down_thresh
            ring_down = lm_array[tip_ids[3]][1] > lm_array[pip_ids[3]][1] + scaled_pointing_down_thresh
            pinky_down = lm_array[tip_ids[4]][1] > lm_array[pip_ids[4]][1] + scaled_pointing_down_thresh
            thumb_tucked_for_point = True 
            if fingers_status[0] == 1 and fingers_status[1] == 1:
                 dist_thumb_index_mcp = self._calculate_distance(lm_array[tip_ids[0]], lm_array[mcp_ids[1]])
                 thumb_tucked_for_point = dist_thumb_index_mcp < (0.1 * (hand_scale_ref/0.15))
            if middle_down and ring_down and pinky_down and thumb_tucked_for_point: gesture_key = "POINT_UP"
            
        # --- PEACE SIGN ---
        if gesture_key == "UNKNOWN_GESTURE" and \
           (fingers_status == [0,1,1,0,0] or \
           (fingers_status[0] == 1 and fingers_status[1] == 1 and fingers_status[2] == 1 and sum(fingers_status[3:]) == 0)):
            # print("GC_DEBUG: Candidate for PEACE.")
            scaled_pointing_down_thresh = self.POINTING_OTHER_FINGERS_DOWN_Y_THRESHOLD * (hand_scale_ref / 0.15)
            ring_down = lm_array[tip_ids[3]][1] > lm_array[pip_ids[3]][1] + scaled_pointing_down_thresh
            pinky_down = lm_array[tip_ids[4]][1] > lm_array[pip_ids[4]][1] + scaled_pointing_down_thresh
            thumb_tucked_for_peace = True
            if fingers_status[0] == 1 and fingers_status[1] == 1 and fingers_status[2] == 1 :
                dist_thumb_index_mcp = self._calculate_distance(lm_array[tip_ids[0]], lm_array[mcp_ids[1]])
                thumb_tucked_for_peace = dist_thumb_index_mcp < (0.12 * (hand_scale_ref/0.15))
            if ring_down and pinky_down and thumb_tucked_for_peace: gesture_key = "PEACE"

        # --- THREE FINGERS UP --- (NEW ONE)
        # elif total_fingers == 3 and fingers_status[1] and fingers_status[2] and fingers_status[3]: # Index, Middle, Ring
        #     gesture_key = "THREE_FINGERS_UP"
            
        # print(f"GC_DEBUG: Final classified gesture_key: {gesture_key}")
        return gesture_key
    
# # gesture_classifier.py
# # Import necessary libraries
# import mediapipe as mp
# import math
# import numpy as np

# # GestureClassifier class for classifying hand gestures based on MediaPipe landmarks
# # This class uses MediaPipe's hand landmarks to determine the gesture being performed by the user.
# # It includes methods for counting fingers, checking conditions for specific gestures,
# # and classifying the gesture based on the landmarks detected.

# class GestureClassifier:
#     #Initializes the GestureClassifier with MediaPipe
#     def __init__(self):
#         self.mp_hands = mp.solutions.hands
#         self.FINGER_UP_Y_THRESHOLD_STRICT = 0.02
#         self.FINGER_UP_Y_THRESHOLD_LOOSE = 0
#         # For X outwards check, relative to thumb's OWN MCP.
#         # Right hand: tip must be to the left of MCP (negative diff). Threshold is negative.
#         # Left hand: tip must be to the right of MCP (positive diff). Threshold is positive.
#         self.THUMB_X_OUTWARDS_MCP_THRESHOLD_RIGHT = -0.02 # Tip X < MCP_X - threshold_abs
#         self.THUMB_X_OUTWARDS_MCP_THRESHOLD_LEFT = 0.02  # Tip X > MCP_X + threshold_abs
#         self.THUMB_UP_Y_VS_MCP_THRESHOLD = 0.03 # Tip must be above MCP by this (scaled)
#         self.FINGER_CURL_Y_MCP_THRESHOLD = 0.015
#         self.THUMB_ACROSS_X_MARGIN = 0.03
#         self.THUMB_Y_ALIGN_MCP_FACTOR = 0.8
#         self.POINTING_OTHER_FINGERS_DOWN_Y_THRESHOLD = 0.02
#         self.THUMBS_UP_CURL_THRESHOLD = 0.01 # Other fingers tip Y > PIP Y + threshold (more curled)

#     # Initializes the MediaPipe Hands solution with default parameters
#     def _get_landmark_list(self, hand_landmarks):
#         return np.array([(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark])

#     def _calculate_distance(self, p1, p2):
#         p1_arr = np.array(p1); p2_arr = np.array(p2)
#         return math.sqrt(np.sum((p1_arr - p2_arr)**2))

#     # Calculates the distance from wrist to middle finger MCP (base knuckle)
#     # Returns a default value if the distance is too small (indicating a potential error)
#     # This is used as a reference scale for finger counting and gesture classification.
#     # If the distance is less than 0.01, it returns a default value of 0.15.
#     # This helps avoid division by zero or very small values in further calculations
#     # and ensures that the scale reference is reasonable for gesture classification.
#     # This is particularly useful for robust finger counting and gesture detection.
#     # The default value of 0.15 is chosen based on typical hand sizes and distances
#     # between the wrist and middle finger MCP in a normal hand.
#     # If the distance is greater than 0.01, it returns the actual distance.
#     # This allows the classifier to adapt to different hand sizes and positions.
#     # If the distance is too small, it assumes a default hand scale reference.
#     # This helps maintain consistent gesture classification across different hand sizes.
#     def _get_wrist_to_middle_mcp_dist(self, lm_array):
#         wrist = lm_array[self.mp_hands.HandLandmark.WRIST]
#         middle_mcp = lm_array[self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
#         dist = self._calculate_distance(wrist, middle_mcp)
#         return dist if dist > 0.01 else 0.15

#     # Counts the number of fingers that are "up" based on MediaPipe landmarks.
#     def _count_fingers_up_robust(self, lm_array, handedness_str, hand_scale_ref):
#         fingers_up_status = [0, 0, 0, 0, 0]
#         tip_ids = [self.mp_hands.HandLandmark.THUMB_TIP, self.mp_hands.HandLandmark.INDEX_FINGER_TIP,
#                    self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP, self.mp_hands.HandLandmark.RING_FINGER_TIP,
#                    self.mp_hands.HandLandmark.PINKY_TIP]
#         pip_ids = [self.mp_hands.HandLandmark.THUMB_IP, self.mp_hands.HandLandmark.INDEX_FINGER_PIP,
#                    self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP, self.mp_hands.HandLandmark.RING_FINGER_PIP,
#                    self.mp_hands.HandLandmark.PINKY_PIP]
#         mcp_ids = [self.mp_hands.HandLandmark.THUMB_MCP, self.mp_hands.HandLandmark.INDEX_FINGER_MCP,
#                    self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP, self.mp_hands.HandLandmark.RING_FINGER_MCP,
#                    self.mp_hands.HandLandmark.PINKY_MCP]

#         # --- Thumb ---
#         thumb_tip = lm_array[tip_ids[0]]
#         thumb_mcp = lm_array[mcp_ids[0]]

#         # Y-condition: Thumb tip is above its MCP (base knuckle)
#         scaled_thumb_y_mcp_thresh = self.THUMB_UP_Y_VS_MCP_THRESHOLD * (hand_scale_ref / 0.15)
#         is_thumb_tip_above_mcp = thumb_tip[1] < thumb_mcp[1] - scaled_thumb_y_mcp_thresh

#         # X-condition: Thumb tip is somewhat outwards from its MCP
#         is_thumb_x_outwards_from_mcp = False
#         if handedness_str == "Right":
#             scaled_x_thresh = self.THUMB_X_OUTWARDS_MCP_THRESHOLD_RIGHT * (hand_scale_ref / 0.15) # Negative
#             is_thumb_x_outwards_from_mcp = thumb_tip[0] < thumb_mcp[0] + scaled_x_thresh # Tip_X < MCP_X - abs_thresh
#         elif handedness_str == "Left":
#             scaled_x_thresh = self.THUMB_X_OUTWARDS_MCP_THRESHOLD_LEFT * (hand_scale_ref / 0.15) # Positive
#             is_thumb_x_outwards_from_mcp = thumb_tip[0] > thumb_mcp[0] + scaled_x_thresh # Tip_X > MCP_X + abs_thresh
        
#         # print(f"DEBUG_THUMB_COUNT: Hand: {handedness_str}, TipY:{thumb_tip[1]:.3f}, McpY:{thumb_mcp[1]:.3f} -> AboveMCP: {is_thumb_tip_above_mcp} (Thresh: {scaled_thumb_y_mcp_thresh:.3f})")
#         # print(f"DEBUG_THUMB_COUNT: TipX:{thumb_tip[0]:.3f}, McpX:{thumb_mcp[0]:.3f} -> X_Outwards: {is_thumb_x_outwards_from_mcp} (ThreshR: {self.THUMB_X_OUTWARDS_MCP_THRESHOLD_RIGHT * (hand_scale_ref / 0.15):.3f}, ThreshL: {self.THUMB_X_OUTWARDS_MCP_THRESHOLD_LEFT * (hand_scale_ref / 0.15):.3f})")

#         if is_thumb_tip_above_mcp and is_thumb_x_outwards_from_mcp:
#             fingers_up_status[0] = 1
#             # print("DEBUG_THUMB_COUNT: Thumb counted as UP.")
            
#         # else: # Add this else for debugging if thumb is not counted up
#             # print(f"DEBUG_THUMB_COUNT: Thumb counted as DOWN. AboveMCP={is_thumb_tip_above_mcp}, XOutwards={is_thumb_x_outwards_from_mcp}")

#         # --- Other Four Fingers --- 
#         for i in range(1, 5):
#             finger_tip_y = lm_array[tip_ids[i]][1]; finger_pip_y = lm_array[pip_ids[i]][1]; finger_mcp_y = lm_array[mcp_ids[i]][1]
#             scaled_strict_thresh = self.FINGER_UP_Y_THRESHOLD_STRICT * (hand_scale_ref / 0.15)
#             scaled_loose_thresh = self.FINGER_UP_Y_THRESHOLD_LOOSE * (hand_scale_ref / 0.15) # Note: LOOSE is 0, so scaled_loose_thresh is also 0
#             cond1_extended = finger_tip_y < finger_pip_y - scaled_strict_thresh
#             # For cond2_generally_up, if scaled_loose_thresh is 0, it becomes tip_y < mcp_y AND pip_y < mcp_y
#             cond2_generally_up = finger_tip_y < finger_mcp_y - scaled_loose_thresh and \
#                                  finger_pip_y < finger_mcp_y - scaled_loose_thresh 
#             if cond1_extended or cond2_generally_up:
#                 fingers_up_status[i] = 1
        
#         total_fingers = sum(fingers_up_status)
#         return fingers_up_status, total_fingers

#     # Classifies the gesture based on the hand landmarks and handedness.
#     # It uses the landmark positions to determine if the gesture is a thumbs up, open palm,
#     # fist, point up, peace sign, or three fingers up.
#     # It returns a string representing the classified gesture.
#     # If no hand landmarks are provided, it returns "NO_HAND".
#     # The classification is based on the positions of the fingertips and their relationships
#     # to the base knuckles (MCPs) and other fingers.
#     def classify(self, hand_landmarks, handedness_str):
#         if not hand_landmarks: return "NO_HAND"
#         lm_array = self._get_landmark_list(hand_landmarks)
#         hand_scale_ref = self._get_wrist_to_middle_mcp_dist(lm_array)
#         fingers_status, total_fingers = self._count_fingers_up_robust(lm_array, handedness_str, hand_scale_ref)
#         gesture_key = "UNKNOWN_GESTURE"
        
#         print(f"Classify - Hand: {handedness_str}, Fingers: {fingers_status}, Total: {total_fingers}, ScaleRef: {hand_scale_ref:.3f}")

#         tip_ids = [self.mp_hands.HandLandmark.THUMB_TIP, self.mp_hands.HandLandmark.INDEX_FINGER_TIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP, self.mp_hands.HandLandmark.RING_FINGER_TIP, self.mp_hands.HandLandmark.PINKY_TIP]
#         pip_ids = [self.mp_hands.HandLandmark.THUMB_IP, self.mp_hands.HandLandmark.INDEX_FINGER_PIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP, self.mp_hands.HandLandmark.RING_FINGER_PIP, self.mp_hands.HandLandmark.PINKY_PIP]
#         mcp_ids = [self.mp_hands.HandLandmark.THUMB_MCP, self.mp_hands.HandLandmark.INDEX_FINGER_MCP, self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP, self.mp_hands.HandLandmark.RING_FINGER_MCP, self.mp_hands.HandLandmark.PINKY_MCP]

#         # --- THUMBS UP ---
#         if fingers_status[0] == 1 and sum(fingers_status[1:]) == 0:
#             # print("GC_DEBUG: Candidate for THUMBS_UP (Initial check: thumb up, others down by count).")
#             scaled_thumbs_up_curl_thresh = self.THUMBS_UP_CURL_THRESHOLD * (hand_scale_ref / 0.15)
#             # Tip Y > PIP Y + thresh means tip is BELOW pip by at least threshold amount
#             index_closed = lm_array[tip_ids[1]][1] > lm_array[pip_ids[1]][1] + scaled_thumbs_up_curl_thresh
#             middle_closed = lm_array[tip_ids[2]][1] > lm_array[pip_ids[2]][1] + scaled_thumbs_up_curl_thresh
#             ring_closed = lm_array[tip_ids[3]][1] > lm_array[pip_ids[3]][1] + scaled_thumbs_up_curl_thresh
#             pinky_closed = lm_array[tip_ids[4]][1] > lm_array[pip_ids[4]][1] + scaled_thumbs_up_curl_thresh
#             # print(f"GC_DEBUG_THUMBS_UP_CURL: I:{index_closed}, M:{middle_closed}, R:{ring_closed}, P:{pinky_closed}")
#             if index_closed and middle_closed and ring_closed and pinky_closed:
#                 # print("GC_DEBUG: THUMBS_UP confirmed by curled fingers.")
#                 if handedness_str == "Right": gesture_key = "THUMB_UP_RIGHT"
#                 elif handedness_str == "Left": gesture_key = "THUMB_UP_LEFT"
#                 else: gesture_key = "THUMB_UP"
        
#         # --- OPEN PALM ---
#         if gesture_key == "UNKNOWN_GESTURE" and total_fingers >= 4:
#             index_tip = lm_array[tip_ids[1]]; middle_tip = lm_array[tip_ids[2]]; ring_tip = lm_array[tip_ids[3]]
#             dist_index_middle = abs(index_tip[0] - middle_tip[0]); dist_middle_ring = abs(middle_tip[0] - ring_tip[0])
#             min_spread_threshold = 0.03 * (hand_scale_ref / 0.15); is_spread = dist_index_middle > min_spread_threshold and dist_middle_ring > min_spread_threshold
#             if total_fingers == 5 or (total_fingers >= 4 and is_spread): gesture_key = "OPEN_PALM"


#         # --- FIST ---
#         if gesture_key == "UNKNOWN_GESTURE" and total_fingers <= 1: 
#             print("GC_DEBUG: Candidate for FIST (total_fingers <= 1).")
#             scaled_curl_thresh_fist = self.FINGER_CURL_Y_MCP_THRESHOLD * (hand_scale_ref / 0.15)
#             index_curled = lm_array[tip_ids[1]][1] > lm_array[mcp_ids[1]][1] + scaled_curl_thresh_fist
#             middle_curled = lm_array[tip_ids[2]][1] > lm_array[mcp_ids[2]][1] + scaled_curl_thresh_fist
#             ring_curled = lm_array[tip_ids[3]][1] > lm_array[mcp_ids[3]][1] + scaled_curl_thresh_fist
#             pinky_curled = lm_array[tip_ids[4]][1] > lm_array[mcp_ids[4]][1] + scaled_curl_thresh_fist
            
#             if index_curled and middle_curled and ring_curled and pinky_curled:
#                 # Now check thumb for fist (if fingers_status[0] was 1, thumb needs to be tucked)
#                 if fingers_status[0] == 0: # Thumb already counted as down by robust counter
#                     gesture_key = "FIST"
#                 elif fingers_status[0] == 1: # Thumb was counted as up, check if it's tucked for a fist
#                     thumb_tip = lm_array[tip_ids[0]]; index_mcp = lm_array[mcp_ids[1]]; pinky_mcp = lm_array[mcp_ids[4]]
#                     scaled_thumb_y_align_fist = abs(index_mcp[1] - lm_array[pip_ids[1]][1]) * self.THUMB_Y_ALIGN_MCP_FACTOR
#                     thumb_y_tucked_fist = thumb_tip[1] > index_mcp[1] - scaled_thumb_y_align_fist
#                     scaled_thumb_x_margin_fist = self.THUMB_ACROSS_X_MARGIN * (hand_scale_ref / 0.15)
#                     thumb_x_across_fist = False
#                     if handedness_str == "Right": thumb_x_across_fist = (index_mcp[0] + scaled_thumb_x_margin_fist > thumb_tip[0] > pinky_mcp[0] - scaled_thumb_x_margin_fist)
#                     elif handedness_str == "Left": thumb_x_across_fist = (pinky_mcp[0] - scaled_thumb_x_margin_fist < thumb_tip[0] < index_mcp[0] + scaled_thumb_x_margin_fist)
#                     dist_thumb_middle_pip = self._calculate_distance(thumb_tip, lm_array[pip_ids[2]])
#                     thumb_close_to_palm_fist = dist_thumb_middle_pip < (0.07 * (hand_scale_ref / 0.15))
#                     if (thumb_x_across_fist or thumb_close_to_palm_fist) and thumb_y_tucked_fist:
#                         gesture_key = "FIST"
#             # if gesture_key == "FIST": print("GC_DEBUG: FIST confirmed.")
        
#         # --- POINT UP ---
#         if gesture_key == "UNKNOWN_GESTURE" and \
#            (fingers_status == [0,1,0,0,0] or \
#            (fingers_status[0] == 1 and fingers_status[1] == 1 and sum(fingers_status[2:]) == 0)):
#             # print("GC_DEBUG: Candidate for POINT_UP.")
#             scaled_pointing_down_thresh = self.POINTING_OTHER_FINGERS_DOWN_Y_THRESHOLD * (hand_scale_ref / 0.15)
#             middle_down = lm_array[tip_ids[2]][1] > lm_array[pip_ids[2]][1] + scaled_pointing_down_thresh
#             ring_down = lm_array[tip_ids[3]][1] > lm_array[pip_ids[3]][1] + scaled_pointing_down_thresh
#             pinky_down = lm_array[tip_ids[4]][1] > lm_array[pip_ids[4]][1] + scaled_pointing_down_thresh
#             thumb_tucked_for_point = True 
#             if fingers_status[0] == 1 and fingers_status[1] == 1:
#                  dist_thumb_index_mcp = self._calculate_distance(lm_array[tip_ids[0]], lm_array[mcp_ids[1]])
#                  thumb_tucked_for_point = dist_thumb_index_mcp < (0.1 * (hand_scale_ref/0.15))
#             if middle_down and ring_down and pinky_down and thumb_tucked_for_point: gesture_key = "POINT_UP"; print("GC_DEBUG: POINT_UP confirmed.")
            
#         # --- PEACE SIGN ---
#         if gesture_key == "UNKNOWN_GESTURE" and \
#            (fingers_status == [0,1,1,0,0] or \
#            (fingers_status[0] == 1 and fingers_status[1] == 1 and fingers_status[2] == 1 and sum(fingers_status[3:]) == 0)):
#             # print("GC_DEBUG: Candidate for PEACE.")
#             scaled_pointing_down_thresh = self.POINTING_OTHER_FINGERS_DOWN_Y_THRESHOLD * (hand_scale_ref / 0.15)
#             ring_down = lm_array[tip_ids[3]][1] > lm_array[pip_ids[3]][1] + scaled_pointing_down_thresh
#             pinky_down = lm_array[tip_ids[4]][1] > lm_array[pip_ids[4]][1] + scaled_pointing_down_thresh
#             thumb_tucked_for_peace = True
#             if fingers_status[0] == 1 and fingers_status[1] == 1 and fingers_status[2] == 1 :
#                 dist_thumb_index_mcp = self._calculate_distance(lm_array[tip_ids[0]], lm_array[mcp_ids[1]])
#                 thumb_tucked_for_peace = dist_thumb_index_mcp < (0.12 * (hand_scale_ref/0.15))
#             if ring_down and pinky_down and thumb_tucked_for_peace: gesture_key = "PEACE"; print("GC_DEBUG: PEACE confirmed.")

#         # --- THREE FINGERS UP --- (NEW ONE)
#         # elif total_fingers == 3 and fingers_status[1] and fingers_status[2] and fingers_status[3]: # Index, Middle, Ring
#         #     gesture_key = "THREE_FINGERS_UP"
            
#         # print(f"GC_DEBUG: Final classified gesture_key: {gesture_key}")
#         return gesture_key