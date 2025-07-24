# pygame_visualizer.py

# Import necessary libraries
import pygame
import math 

# PygameVisualizer class for visualizing a simple robot simulation
# This class creates a Pygame window, handles robot movement, and draws the robot's state on the screen.
# It includes methods for handling input, updating the robot's state, drawing the robot, and closing the Pygame window.
# The robot can move forward, backward, and turn left or right based on commands.
# The robot's position wraps around the screen edges,
# allowing it to appear on the opposite side if it moves out of bounds.

class PygameVisualizer:
    # Initializes the Pygame window and sets up initial parameters for the robot.
    # Parameters:
    # - width: Width of the Pygame window (default 600)
    # - height: Height of the Pygame window (default 400)
    # - title: Title of the Pygame window (default "Robot Simulator")
    # Initializes colors, robot parameters, and font for displaying text.
    # Sets the initial position and angle of the robot at the center of the window.
    # Sets the robot's speed and turn speed for movement.
# Initializes the running state of the visualizer.
    def __init__(self, width=600, height=400, title="Robot Simulator"):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(title)

        # Initialize colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (255, 0, 0)
        self.GREEN = (0, 200, 0)

        # Initialize dummy "robot" parameters
        self.robot_radius = 15
        self.robot_x = self.width // 2
        self.robot_y = self.height // 2
        self.robot_angle = 0
        self.robot_speed = 3
        self.robot_turn_speed = 5

        # Initialize font for displaying text
        self.font = pygame.font.SysFont(None, 36)
        self.is_running = True

    # Handles input events from the Pygame event queue.
    # Checks for quit events and key presses to control the robot.
    # Specifically checks for the "Q" key to quit the application.
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("Quit event received! Closing Pygame window.")
                self.is_running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    print("Quit command received! Closing Pygame window.")
                    self.is_running = False

    def update_robot_state(self, command):
        if not self.is_running: return
        dx, dy, d_angle = 0, 0, 0
        
        # Determine the robot's movement based on the command
        
        # Move forward continuously or go forward
        if  command == "GO_FORWARD":
            rad_angle = math.radians(self.robot_angle)
            dx = self.robot_speed * math.cos(rad_angle)
            dy = self.robot_speed * math.sin(rad_angle)
        # Move backward
        elif command == "MOVE_BACKWARD":
            rad_angle = math.radians(self.robot_angle)
            dx = -self.robot_speed * math.cos(rad_angle)
            dy = -self.robot_speed * math.sin(rad_angle)
        # Turn left
        elif command == "TURN_LEFT":
            d_angle = self.robot_turn_speed
        # Turn right
        elif command == "TURN_RIGHT":
            d_angle = -self.robot_turn_speed
        # elif command == "STOP" or command == "NO_ACTION" or command is None:
            # dx, dy, d_angle remain 0, so robot stops
            # pass

        self.robot_x += dx
        self.robot_y += dy
        self.robot_angle = (self.robot_angle + d_angle) % 360

        if self.robot_x < 0: self.robot_x = self.width
        if self.robot_x > self.width: self.robot_x = 0
        if self.robot_y < 0: self.robot_y = self.height
        if self.robot_y > self.height: self.robot_y = 0

    # Draws the robot and its current state on the Pygame window.
    def draw(self, current_command_text="Command: NONE"):
        if not self.is_running: return
        self.screen.fill(self.BLACK)
        
        # Draw the robot as a circle and its direction as a line
        pygame.draw.circle(self.screen, self.GREEN, (int(self.robot_x), int(self.robot_y)), self.robot_radius)
        line_length = self.robot_radius * 1.5
        rad_angle = math.radians(self.robot_angle)
        end_x = self.robot_x + line_length * math.cos(rad_angle)
        end_y = self.robot_y + line_length * math.sin(rad_angle)
        
        # Draw the direction line
        pygame.draw.line(self.screen, self.RED, (int(self.robot_x), int(self.robot_y)), (int(end_x), int(end_y)), 3)
        text_surface = self.font.render(current_command_text, True, self.WHITE)
        self.screen.blit(text_surface, (10, 10))
        pygame.display.flip()

    def close(self):
        pygame.quit()