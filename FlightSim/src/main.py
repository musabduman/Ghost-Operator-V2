import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
from settings import *
from aircraft import Aircraft
from utils import get_controls
from environment import draw_runway

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption('FlightSim - Basit Uçuş Simülatörü')
    clock = pygame.time.Clock()
    aircraft = Aircraft(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 120)
    running = True
    frame_count = 0
    while running and frame_count < 120:  # 2 saniye çalıştır (FPS 60)
        dt = clock.get_time() / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        controls = get_controls()
        aircraft.update(dt, controls)
        screen.fill((135, 206, 235))
        draw_runway(screen, WINDOW_WIDTH, WINDOW_HEIGHT)
        aircraft.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)
        frame_count += 1
    pygame.quit()
    print('Simulation ran for', frame_count, 'frames')

if __name__ == '__main__':
    main()
