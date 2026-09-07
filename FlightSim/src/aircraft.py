import pygame
from settings import *

class Aircraft:
    def __init__(self, x, y):
        self.pos = pygame.math.Vector2(x, y)
        self.vel = pygame.math.Vector2(0, 0)
        self.angle = 0
        self.throttle = 0.0
        self.elevator = 0.0
        self.aileron = 0.0
        self.rudder = 0.0
        self.image = pygame.Surface((40, 20), pygame.SRCALPHA)
        pygame.draw.polygon(self.image, (200, 0, 0), [(0, 0), (40, 10), (0, 20)])
        self.rect = self.image.get_rect(center=self.pos)

    def update(self, dt, controls):
        """Update aircraft physics.
        dt: delta time in seconds.
        controls: dict with throttle, elevator, aileron, rudder.
        """
        self.throttle = controls.get('throttle', self.throttle)
        self.elevator = controls.get('elevator', self.elevator)
        self.aileron = controls.get('aileron', self.aileron)
        self.rudder = controls.get('rudder', self.rudder)

        thrust = MAX_THRUST * self.throttle
        air_speed = self.vel.length()
        lift = 0.5 * AIR_DENSITY * (air_speed ** 2) * LIFT_COEFFICIENT
        drag = 0.5 * AIR_DENSITY * (air_speed ** 2) * DRAG_COEFFICIENT

        thrust_vec = pygame.math.Vector2(thrust, 0).rotate(-self.angle)
        lift_vec = pygame.math.Vector2(0, -lift).rotate(-self.angle)
        # Drag opposite to velocity direction without using normalize (avoid NaN)
        if air_speed > 0:
            drag_vec = -self.vel * (drag / air_speed)
        else:
            drag_vec = pygame.math.Vector2(0, 0)

        force = thrust_vec + lift_vec + drag_vec
        accel = force  # mass = 1 kg
        self.vel += accel * dt
        self.vel.y += GRAVITY * dt
        self.pos += self.vel * dt
        self.angle += self.elevator * 30 * dt

        # Clamp position to 32‑bit int range
        max_int = 2_147_483_647
        min_int = -2_147_483_648
        self.pos.x = max(min(self.pos.x, max_int), min_int)
        self.pos.y = max(min(self.pos.y, max_int), min_int)

        self.rect.center = (int(round(self.pos.x)), int(round(self.pos.y)))

    def draw(self, surface):
        rotated = pygame.transform.rotate(self.image, self.angle)
        new_rect = rotated.get_rect(center=self.pos)
        surface.blit(rotated, new_rect.topleft)

__all__ = ['Aircraft']
