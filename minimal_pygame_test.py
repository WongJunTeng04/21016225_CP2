import pygame
import time

pygame.init()
screen = pygame.display.set_mode((300, 200))
pygame.display.set_caption("Minimal Pygame Test")
running = True
start_time = time.time()

print("Minimal Pygame Test Started. Window should stay open.")
print("Press ESC or close window to quit.")

while running:
    for event in pygame.event.get():
        print(f"PYGAME_MINIMAL: Event received: {event}")
        if event.type == pygame.QUIT:
            print("PYGAME_MINIMAL: pygame.QUIT event received!")
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print("PYGAME_MINIMAL: ESCAPE key pressed!")
                running = False
    
    screen.fill((0,0,0)) # Black
    pygame.display.flip()

    if time.time() - start_time > 30: # Automatically quit after 30 seconds if not manually closed
        print("PYGAME_MINIMAL: Test running for 30 seconds, auto-quitting.")
        # running = False # Let's see if it quits before this
        pass # Keep it running to see if it quits on its own

    time.sleep(0.01)

print("Minimal Pygame Test Exiting.")
pygame.quit()