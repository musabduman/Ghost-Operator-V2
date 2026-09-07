import pygame
from settings import *

class Aircraft:
    def __init__(self, x, y):
        # Konum ve hız
        self.pos = pygame.math.Vector2(x, y)
        self.vel = pygame.math.Vector2(0, 0)
        self.angle = 0  # derece
        # Kontrol durumları
        self.throttle = 0.0  # 0-1
        self.elevator = 0.0  # -1 (nose down) to 1 (nose up)
        self.aileron = 0.0   # -1 (roll left) to 1 (roll right)
        self.rudder = 0.0    # -1 to 1
        # Görsel placeholder (basit dikdörtgen)
        self.image = pygame.Surface((40, 20), pygame.SRCALPHA)
        pygame.draw.polygon(self.image, (200, 0, 0), [(0, 0), (40, 10), (0, 20)])
        self.rect = self.image.get_rect(center=self.pos)

    def update(self, dt, controls):
        """dt: saniye cinsinden delta time, controls dict içinde kontrol değerleri"""
        # Kontrolleri güncelle
        self.throttle = controls.get('throttle', self.throttle)
        self.elevator = controls.get('elevator', self.elevator)
        self.aileron = controls.get('aileron', self.aileron)
        self.rudder = controls.get('rudder', self.rudder)
        # Basit fizik: itme, kaldırma, sürükleme
        thrust = MAX_THRUST * self.throttle
        # Hava hızı
        air_speed = self.vel.length()
        # Kaldırma = 0.5 * rho * v^2 * S * Cl (S = referans alan, basit 1)
        lift = 0.5 * AIR_DENSITY * (air_speed ** 2) * LIFT_COEFFICIENT
        # Sürükleme = 0.5 * rho * v^2 * S * Cd
        drag = 0.5 * AIR_DENSITY * (air_speed ** 2) * DRAG_COEFFICIENT
        # İtme yönü (uçak başı yönü)
        thrust_vec = pygame.math.Vector2(thrust, 0).rotate(-self.angle)
        # Kaldırma dikey (yukarı doğru, ekran koordinatında -y)
        lift_vec = pygame.math.Vector2(0, -lift).rotate(-self.angle)
        # Drag ters yönde
        drag_vec = -self.vel.normalize() * drag if air_speed != 0 else pygame.math.Vector2(0,0)
        # Net kuvvet
        force = thrust_vec + lift_vec + drag_vec
        # ivme = force / mass (basit 1 kg)
        accel = force  # mass=1
        self.vel += accel * dt
        # Yerçekimi etkisi (yukarı yön negatif)
        self.vel.y += GRAVITY * dt
        # Pozisyon güncelle
        self.pos += self.vel * dt
        # Açıyı kontrol (elevator etkisi)
        self.angle += self.elevator * 30 * dt  # 30 deg/s max
        # Rect güncelle
        self.rect.center = self.pos

    def draw(self, surface):
        rotated = pygame.transform.rotate(self.image, self.angle)
        new_rect = rotated.get_rect(center=self.pos)
        surface.blit(rotated, new_rect.topleft)

__all__ = ['Aircraft']
