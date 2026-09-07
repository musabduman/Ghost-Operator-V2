import pygame

def draw_background(surface):
    # Gökyüzü (sky blue) zaten main'de dolduruluyor, burada ek bulut vs. ekleyebiliriz
    pass

def draw_runway(surface, width, height):
    # Basit pist: orta çizgi ve iki kenar çizgisi
    runway_color = (50, 50, 50)
    pygame.draw.rect(surface, runway_color, pygame.Rect(0, height - 100, width, 100))
    # Orta çizgi
    line_color = (255, 255, 255)
    for x in range(0, width, 40):
        pygame.draw.line(surface, line_color, (x, height - 50), (x + 20, height - 50), 2)

__all__ = ['draw_background', 'draw_runway']
