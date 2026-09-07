import pygame

def get_controls():
    """Klavye durumuna göre kontrol dict döndürür.
    throttle: W (artır), S (azalt)
    elevator: Up/Down
    aileron: A/D
    rudder: Q/E
    """
    keys = pygame.key.get_pressed()
    controls = {
        'throttle': 1.0 if keys[pygame.K_w] else (0.0 if keys[pygame.K_s] else 0.5),
        'elevator': -1.0 if keys[pygame.K_UP] else (1.0 if keys[pygame.K_DOWN] else 0.0),
        'aileron': -1.0 if keys[pygame.K_a] else (1.0 if keys[pygame.K_d] else 0.0),
        'rudder': -1.0 if keys[pygame.K_q] else (1.0 if keys[pygame.K_e] else 0.0),
    }
    return controls

__all__ = ['get_controls']
